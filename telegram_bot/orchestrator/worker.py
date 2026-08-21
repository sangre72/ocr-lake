"""자동 워커 — 봇이 새 u_ 를 감지하면 a_ 지시서로 변환한 뒤 `claude -p` 워커를 spawn 해 처리.

배경 (유저 지시 2026-08-05):
- 1차: "봇이 식별하면 에이전트에게 할당" (세션 자동깨움 §9-0 대체).
- 2차 교정: "claude -p 헤드리스는 매번 맥락 없는 새 세션 → 프로젝트 연결성 부족.
  봇이 u_ 를 그냥 claude -p 에 던지지 말고, a_ 지시서로 변환 후 워커가 그걸 처리하라."
  → a_ 지시서가 '맥락 발판' 이 되어 워커가 프로젝트 컨텍스트를 파악할 발판을 갖는다.

흐름 (och.txt §5 워크플로우 정합):
  봇: 새 u_ 감지 → a_{NN}_auto.txt 지시서 생성(유저 원문 + CHAT_ID + WORKER_MODE + parent u_ 링크)
      → 워커 spawn ("protocol/a/a_{NN} 를 읽고 이 프로젝트 코드 컨텍스트로 처리하라")
  워커(claude -p, cwd=repo): a_ 읽고 정제·(코드작업)·처리 → ar_{NN}_auto.txt 응답 남김([STATUS] done)
  봇: relay_worker_responses() 가 ar_ 종결 STATUS 감지 → 유저에게 텔레그램 회신 + archive

무손실·안죽음 (och.txt 제2원칙):
- spawn 은 detached. 실패·claude 미설치 등은 (False, 사유) 로 반환 → 봇 루프가 안 죽는다.
- 중복 방지: u_ → a_ 1:1 매핑. 대응 a_(같은 SEQ)가 이미 있으면 재생성·재spawn 안 함.
  a_ 는 디스크에 영속 → 봇 재시작에도 중복 없음. (a_→ar_ 로 처리완료 판정은 기존 relay 가 담당.)
- 도입 시점의 과거 u_(수십 개)는 seed 로 '처리됨' 마킹해 spawn 폭주를 막는다(신규만 처리).
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import protocol_store as ps

_HERE = Path(__file__).resolve().parent            # telegram_bot/orchestrator
_REPO_ROOT = Path(__file__).resolve().parents[2]   # repo 루트 자동도출(워커 cwd = 코드 컨텍스트, 프로젝트 불문)

# u_ 도입 이전 과거요청 seed 마커 디렉토리 (u_ basename → '이미 처리됨' 표시).
# ※ 신규 u_ 의 '처리됨' 판정은 대응 a_ 존재로 한다(1:1). 이 디렉토리는 seed 전용.
_SEED_DIR = ps.U_DIR / ".dispatched"
_SEED_SENTINEL = _SEED_DIR / ".seeded"
# 워커 로그 디렉토리.
_LOG_DIR = _REPO_ROOT / "logs" / "workers"
# 배정 보류(hold) 마커 — 캡션 없는 사진처럼 뒤이을 텍스트를 기다리는 u_ 의 조기배정 방지.
_HOLD_DIR = ps.U_DIR / ".hold"
# ★오케 전용(orch-only) 마커 — 봇이 만든 '오케 경유 신호' u_ (인라인 버튼답변·씬선별 콜백,
# needs-info 에 대한 유저답 등)는 워커 실작업이 아니라 오케 세션이 소비할 신호다.
# 이 마커가 찍힌 u_ 는 봇의 자동배정(dispatch)에서 영구 제외한다.
# 근거(och 제4원칙 + u_144 사고): 봇이 신호성 u_ 까지 워커로 spawn 하면 신호가 실작업으로
# 오분류돼 오케의 정제·관제를 건너뛴다. → 봇은 '실작업 u_'만 자동처리, '신호 u_'는 오케 전용.
_ORCH_ONLY_DIR = ps.U_DIR / ".orch_only"

# 동시 워커 상한. ★기본=1 (순차처리) — 유저 지시 2026-08-05 u_149 "충돌 위험? 순차처리해".
# 근거(och P0.5 예외규정): 기본은 병렬이나 "같은 파일 동시수정 충돌(→worktree 격리 or 순차)"은
# 직렬이 정당하다. 자동워커는 전부 같은 repo(cwd=_REPO_ROOT)에서 코드를 수정하므로 병렬 spawn 시
# 같은 소스/DB/git 인덱스를 동시에 건드려 충돌한다 → 기본을 1(한 번에 하나)로 직렬화한다.
# 미처리 u_ 는 상한에 걸려도 유실 없이 다음 폴링에서 순서대로 처리된다(dispatch_pending 무손실).
# 병렬이 안전한 환경(워커별 worktree 격리 등)에서만 ORCH_MAX_WORKERS 를 올린다.
MAX_CONCURRENT = int(os.environ.get("ORCH_MAX_WORKERS", "1"))

# 봇의 무조건 u_ 자동 dispatch 게이트 (och 제4원칙 — 오케 경유, 유저 지시 2026-08-05 "땜빵 말고 최선의 방법").
# ★기본=off: 봇은 새 u_ 를 저장 + 접수피드백까지만 하고, u_ 원문을 워커에 직결하지 않는다.
#   → 오케 세션이 §9-0 으로 깨어나 u_ 를 정제→a_ 지시서 작성→워커 배정하는 흐름으로 일원화.
#   근거(u_144 사고): 봇(비-LLM)이 실작업/승인/피드백을 구분 못 한 채 u_ 원문을 워커로 spawn 하면
#   신호성 요청까지 워커가 붙들어 매달리고, 오케의 정제·관제를 건너뛴다(제4원칙 위반·좀비 유발).
# on(ORCH_AUTO_DISPATCH=1|true|on|yes)일 때만 과거처럼 봇이 u_ 를 자동 spawn(과도기 호환용).
# ※ 오케가 명시적으로 만든 [WORKER_MODE] auto a_ 는 이 게이트와 무관하게 spawn_for_task 로 실행된다.
def _auto_dispatch_enabled() -> bool:
    return os.environ.get("ORCH_AUTO_DISPATCH", "off").strip().lower() in (
        "1", "true", "on", "yes",
    )

# 자동워커 멈춤 감지 타임아웃(초). 기본 10분.
# 근거: 단발 자동워커는 보통 수 분 내 끝난다. 장시간 작업(영상 등)은 워커가
# ar_ 의 [HEARTBEAT]/[STATUS] in-progress 를 갱신하므로, 아래 _elapsed_since_signal()
# 이 "마지막 생존신호(=ar_ mtime) 이후 경과"로 판정해 살아있는 동안은 타임아웃이 리셋된다.
# → 실제로 '멈춘'(신호 끊긴) 워커만 정리한다. .env 의 ORCH_WORKER_TIMEOUT_SEC 로 조정.
WORKER_TIMEOUT = int(os.environ.get("ORCH_WORKER_TIMEOUT_SEC", "600"))
# SIGTERM 후 SIGKILL 까지 유예(초) — 그레이스풀 종료 기회.
_TERM_GRACE_SEC = float(os.environ.get("ORCH_WORKER_TERM_GRACE_SEC", "5"))

_SEED_DIR.mkdir(parents=True, exist_ok=True)
_HOLD_DIR.mkdir(parents=True, exist_ok=True)
_ORCH_ONLY_DIR.mkdir(parents=True, exist_ok=True)
_LOG_DIR.mkdir(parents=True, exist_ok=True)


# ---------- claude 바이너리 ----------

def claude_bin() -> str | None:
    """claude 실행파일 경로 (없으면 None). PATH + 흔한 설치 위치를 함께 탐색."""
    found = shutil.which("claude")
    if found:
        return found
    for cand in (
        Path.home() / ".npm-global" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
        Path("/opt/homebrew/bin/claude"),
    ):
        if cand.exists():
            return str(cand)
    return None


# ---------- SEQ / 매핑 헬퍼 ----------

def _seq_of(u_path: Path) -> str | None:
    """u_{NN}_... 파일명에서 2자리 SEQ 문자열 추출."""
    m = re.match(r"u_(\d+)_", u_path.name)
    return m.group(1) if m else None


# 오케 세션이 처리 완료한 u_ 목록 (감시 데몬/세션이 append). 봇은 여기 있으면 재배정 안 함.
# ★세션↔봇 중복판정 통일(u_162): 세션은 seen 으로, 봇은 _SEED_DIR 로 따로 판정하다 u_153 이중처리 발생.
# → 봇도 seen 을 존중해, 세션이 이미 처리한 u_ 를 자동배정에서 제외한다.
_SEEN_FILE = _REPO_ROOT / "logs" / ".orch_seen_u"


def _is_seen_by_session(u_name: str) -> bool:
    """오케 세션이 이미 처리(seen 등록)한 u_ 인가 — 봇 재배정 차단용."""
    try:
        if not _SEEN_FILE.exists():
            return False
        for line in _SEEN_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip() == u_name:
                return True
    except OSError:
        pass
    return False


def has_dispatch(u_path: Path) -> bool:
    """이 u_ 에 대응하는 a_ 지시서가 이미 있는가 (같은 SEQ 의 a_*.txt).

    a_ 존재 = '워커에게 배정됨' = 중복 spawn 금지. relay 가 a_/ar_ 로 완료를 판정한다.
    seed 마커가 있어도 배정하지 않은 것으로 본다(과거요청 제외).
    """
    seq = _seq_of(u_path)
    if seq is None:
        return True  # 형식 이상 → 건드리지 않음(안전)
    if _is_seen_by_session(u_path.name):
        return True  # ★오케 세션이 이미 처리(seen) — 봇 재배정 금지(u_153 이중처리 방지, u_162)
    if (_SEED_DIR / u_path.name).exists():
        return True  # 도입 이전 과거요청 — 처리 대상 아님
    if is_orch_only(u_path):
        return True  # ★오케 전용 신호(버튼답변·씬선별·needs-info 답) — 봇 자동배정 금지(제4원칙)
    if (_HOLD_DIR / u_path.name).exists():
        return True  # 배정 보류 중(뒤이을 텍스트 대기) — 아직 배정 안 함
    for a in ps.A_DIR.glob(f"a_{seq}_*.txt"):
        return True
    return False


def seed_existing_if_needed() -> int:
    """최초 1회: 현재 존재하는 모든 u_ 를 seed 마킹(과거요청 제외).

    이 기능 도입 시점의 과거 u_ 가 한꺼번에 a_ 생성·spawn 되는 것을 막는다.
    반환: seed 한 개수(0=이미 seed됨).
    """
    if _SEED_SENTINEL.exists():
        return 0
    n = 0
    for u in ps.U_DIR.glob("u_*.txt"):
        marker = _SEED_DIR / u.name
        if not marker.exists():
            marker.write_text(
                datetime.now().isoformat(timespec="seconds"), encoding="utf-8"
            )
            n += 1
    _SEED_SENTINEL.write_text(
        datetime.now().isoformat(timespec="seconds"), encoding="utf-8"
    )
    return n


def mark_dispatched(u_path: Path) -> None:
    """u_ 를 '배정됨'으로 영속 마킹(a_ 가 done/ 으로 아카이브돼도 재배정 방지).

    has_dispatch 가 이 마커(_SEED_DIR)를 검사하므로, 한 번 spawn 된 u_ 는
    a_ 위치와 무관하게 다시 배정되지 않는다(중복 spawn 근본 차단).
    """
    (_SEED_DIR / u_path.name).write_text(
        datetime.now().isoformat(timespec="seconds"), encoding="utf-8"
    )


def mark_orch_only(u_path: Path | None) -> None:
    """u_ 를 '오케 전용 신호'로 영속 마킹 → 봇 자동배정에서 영구 제외(제4원칙).

    봇이 인라인 버튼답변·씬선별 콜백 등 '오케 경유 신호'를 u_ 로 남길 때 호출한다.
    이런 u_ 는 워커 실작업이 아니라 오케 세션이 읽어 판단할 신호이므로 spawn 하지 않는다.
    """
    if u_path is None:
        return
    (_ORCH_ONLY_DIR / u_path.name).write_text(
        datetime.now().isoformat(timespec="seconds"), encoding="utf-8"
    )


def is_orch_only(u_path: Path) -> bool:
    """이 u_ 가 '오케 전용 신호'로 마킹돼 봇 자동배정 대상에서 제외되는가."""
    return (_ORCH_ONLY_DIR / u_path.name).exists()


def hold_dispatch(u_path: Path | None) -> None:
    """u_ 의 자동배정을 보류(캡션 없는 사진 → 뒤이을 텍스트 대기). release 로 해제."""
    if u_path is None:
        return
    (_HOLD_DIR / u_path.name).write_text(
        datetime.now().isoformat(timespec="seconds"), encoding="utf-8"
    )


def release_dispatch(u_path: Path | None) -> None:
    """보류 해제 — 다음 루프에서 이 u_ 가 자동배정 대상이 된다."""
    if u_path is None:
        return
    m = _HOLD_DIR / u_path.name
    try:
        m.unlink()
    except OSError:
        pass


def find_undispatched() -> list[Path]:
    """아직 a_ 배정이 없는 u_ 목록 (SEQ 오름차순)."""
    out = [u for u in ps.U_DIR.glob("u_*.txt") if not has_dispatch(u)]
    out.sort(key=lambda p: p.name)
    return out


# ---------- 동시성 · 좀비/타임아웃 관리 (och 제2원칙 — 죽으면 안 됨) ----------


@dataclass
class _Job:
    """실행 중인 자동워커 1건. spawn 시각·a_ 경로를 함께 보관해
    (1) 좀비 명시적 reap, (2) 멈춤 타임아웃 판정, (3) 실패 시 ar_ error 기록에 쓴다.
    """
    proc: subprocess.Popen
    a_path: Path
    started_at: float = field(default_factory=time.monotonic)


_running: list[_Job] = []


def _ar_path_for(a_path: Path) -> Path | None:
    """a_{NN}_{topic}.txt → 짝 ar_{NN}_{topic}.txt 경로."""
    m = re.match(r"a_(\d+)_(.+)\.txt", a_path.name)
    if not m:
        return None
    return ps.A_DIR / f"ar_{m.group(1)}_{m.group(2)}.txt"


def _elapsed_since_signal(job: _Job) -> float:
    """마지막 '생존신호' 이후 경과(초).

    생존신호 = ar_ 파일의 mtime(워커가 [HEARTBEAT]/[STATUS] 를 갱신하면 mtime 이 오른다).
    ar_ 가 아직 없으면 spawn 이후 경과로 판정. spawn 시각(monotonic)과 ar_ mtime 중
    더 최근을 기준으로 삼아, 하트비트가 갱신되는 동안은 타임아웃이 리셋되게 한다.
    (단순 spawn 고정보다 견고 — 장시간 작업의 오탐 방지.)
    """
    now = time.monotonic()
    elapsed = now - job.started_at
    ar = _ar_path_for(job.a_path)
    if ar is not None and ar.exists():
        try:
            # wall-clock mtime → monotonic 기준 경과로 환산.
            age = time.time() - ar.stat().st_mtime
            if age < elapsed:
                elapsed = age
        except OSError:
            pass
    return elapsed


def _reap(job: _Job) -> None:
    """죽은(또는 방금 죽인) 자식을 명시적으로 거둔다(<defunct> 방지).

    poll() 이 반환코드를 회수하지만, 외부 kill 로 죽은 자식도 확실히 거두기 위해
    최대한 wait() 을 시도한다(짧은 타임아웃). 예외는 삼켜 루프를 보호.
    """
    try:
        job.proc.wait(timeout=0.1)
    except Exception:  # noqa: BLE001 (TimeoutExpired 포함 — 이미 poll 로 종료 확인된 경우만 호출됨)
        pass


def _kill_job(job: _Job, reason: str) -> None:
    """멈춘/정리대상 자식을 프로세스그룹째 SIGTERM→(유예)→SIGKILL 로 종료 후 reap.

    start_new_session=True 로 띄웠으므로 os.killpg 로 자식의 자식까지 정리한다.
    """
    proc = job.proc
    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, OSError):
        pgid = None

    def _sig(sig: int) -> None:
        try:
            if pgid is not None:
                os.killpg(pgid, sig)
            else:
                proc.send_signal(sig)
        except (ProcessLookupError, OSError):
            pass

    # 1) 그레이스풀: SIGTERM 후 유예 대기.
    _sig(signal.SIGTERM)
    deadline = time.monotonic() + _TERM_GRACE_SEC
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    # 2) 살아있으면 강제 종료.
    if proc.poll() is None:
        _sig(signal.SIGKILL)
    _reap(job)


def _record_timeout_error(job: _Job, elapsed: float) -> None:
    """타임아웃으로 정리된 워커의 a_ 에 대응하는 ar_ 를 [STATUS] error 로 기록.

    → 봇 relay_worker_responses() 가 이 error 를 유저에게 회신하고 아카이브한다
    (무손실·자동회복). 이미 ar_ 가 있으면(needs-info 등) 덮어쓰지 않는다.
    """
    ar = _ar_path_for(job.a_path)
    if ar is None:
        return
    if ar.exists():
        # 워커가 뭔가 남겼다면(needs-info/in-progress) 존중 — 덮어쓰지 않는다.
        # 단 in-progress 인데 프로세스가 이미 죽었으면 error 로 교정한다.
        try:
            status = ps.read_response_status(ar)
        except Exception:  # noqa: BLE001
            return
        if status != "in-progress":
            return
    body = (
        "[STATUS] error\n"
        f"[HEARTBEAT] {datetime.now().strftime('%H:%M')} 타임아웃 정리\n\n"
        "## 결과\n"
        f"자동워커가 응답 없이 멈춰(마지막 생존신호 이후 약 {int(elapsed)}s 경과) "
        f"타임아웃({WORKER_TIMEOUT}s)으로 정리되었습니다. 요청을 다시 시도해 주세요.\n"
    )
    try:
        ar.write_text(body, encoding="utf-8")
    except OSError:
        pass


def _prune_running() -> int:
    """실행 중 목록을 훑어 (1) 죽은 자식 reap, (2) 멈춘(타임아웃) 자식 정리.

    매 봇 루프에서 호출된다(유휴 시에도 relay 경로에서 running_count 로 호출됨).
    반환: 살아있는 워커 수. 예외는 개별 job 단위로 삼켜 루프를 보호한다.
    """
    global _running
    alive: list[_Job] = []
    for job in _running:
        try:
            if job.proc.poll() is not None:
                # 이미 종료 — 명시적 reap 으로 <defunct> 제거.
                _reap(job)
                continue
            elapsed = _elapsed_since_signal(job)
            if elapsed > WORKER_TIMEOUT:
                # 멈춤(신호 끊김) — 정리 + ar_ error 기록(무손실 회복).
                _kill_job(job, reason=f"timeout>{WORKER_TIMEOUT}s")
                _record_timeout_error(job, elapsed)
                continue
            alive.append(job)
        except Exception:  # noqa: BLE001 — 한 job 문제로 전체 prune 이 죽지 않게.
            alive.append(job)
    _running = alive
    return len(_running)


def running_count() -> int:
    return _prune_running()


def shutdown_all() -> None:
    """봇 종료 시 실행 중 자동워커를 모두 정리(그레이스풀 셧다운, 고아 방지).

    atexit + SIGTERM 핸들러에서 호출. 예외를 삼켜 종료 경로를 막지 않는다.
    """
    global _running
    jobs, _running = _running, []
    for job in jobs:
        try:
            if job.proc.poll() is None:
                _kill_job(job, reason="bot-shutdown")
            else:
                _reap(job)
        except Exception:  # noqa: BLE001
            pass


_shutdown_installed = False


def install_shutdown_hooks() -> None:
    """봇 프로세스가 죽을 때 자식 워커를 고아로 남기지 않도록 훅 설치(1회).

    - atexit: 정상 종료·SystemExit 시 정리.
    - SIGTERM: 데몬 매니저/kill 종료 시 정리 후 기본동작(프로세스 종료)로 이어감.
    (SIGINT 은 KeyboardInterrupt→atexit 로 커버되므로 별도 설치하지 않는다.)
    """
    global _shutdown_installed
    if _shutdown_installed:
        return
    atexit.register(shutdown_all)

    def _on_term(signum, frame):  # noqa: ANN001
        shutdown_all()
        # 기본 SIGTERM 동작 복원 후 자기 자신에 재전달 → 정상 종료.
        try:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            os.kill(os.getpid(), signal.SIGTERM)
        except Exception:  # noqa: BLE001
            raise SystemExit(0)

    try:
        signal.signal(signal.SIGTERM, _on_term)
    except (ValueError, OSError):
        # 메인 스레드가 아니면 signal 설치 불가 — atexit 만으로도 무방.
        pass
    _shutdown_installed = True


# ---------- a_ 지시서 생성 (맥락 발판) ----------

def _short(text: str, n: int = 40) -> str:
    t = " ".join(text.split())
    return (t[:n] + "…") if len(t) > n else t


def build_task_from_user(u_path: Path) -> Path | None:
    """u_ 유저요청 → a_{NN}_auto.txt 지시서 생성 (맥락 발판).

    봇은 LLM 이 아니라 정교한 정제는 못 하지만, u_ 원문을 a_ 틀에 옮기고
    [CHAT_ID]·[WORKER_MODE]·[PARENT] 를 채워 워커가 맥락을 파악할 발판을 만든다.
    반환: 생성한 a_ 경로 (실패 시 None).
    """
    seq = _seq_of(u_path)
    if seq is None:
        return None
    text = u_path.read_text(encoding="utf-8")
    chat_id = ps.read_field(u_path, "CHAT_ID")
    username = ps.read_field(u_path, "USERNAME")
    ref_image = ps.read_field(u_path, "REF_IMAGE")
    # u_ 의 '## 원문' 섹션만 뽑아 유저 요청 본문으로.
    m = re.search(r"##\s*원문\s*\n(.+)\Z", text, re.S)
    body = (m.group(1).strip() if m else text.strip())
    u_rel = ps.rel_from_repo(u_path)

    title = _short(body or username or "요청", 40)
    a_path = ps.A_DIR / f"a_{seq}_auto.txt"
    ref_line = f"[REF_IMAGE] {ref_image}\n" if ref_image else ""
    content = (
        "[TYPE] auto\n"
        "[PRIORITY] normal\n"
        f"[TITLE] {title}\n"
        f"[CHAT_ID] {chat_id}\n"
        f"[USERNAME] {username}\n"
        "[WORKER_MODE] auto\n"
        f"[PARENT] {u_rel}\n"
        f"{ref_line}"
        "\n"
        "## 지시\n"
        f"아래 유저 요청을 이 프로젝트({_REPO_ROOT}) 코드 컨텍스트로 정제·처리하라.\n"
        "소스/파일을 읽거나 고쳐야 하는 작업이면 실제로 수행하고, 단순 질문이면 답을 작성한다.\n"
        ".claude/rules(있으면: 보안·네이밍·디자인·접근성·코드구조·기능일관성 등) 및 och.txt(§4·§7) 준수.\n"
        f"네트워크/npm/playwright 재설치 금지. 작업 범위는 {_REPO_ROOT} 안으로 한정.\n"
        "\n"
        "## 유저 원문\n"
        f"{body}\n"
        "\n"
        "## 응답 방법 (봇이 이걸 감지해 유저에게 회신한다)\n"
        f"- 이 파일과 같은 폴더에 ar_{seq}_auto.txt 를 만들어라(같은 번호·접미사).\n"
        "- 첫 줄: [STATUS] done  (실패 시 error|blocked, 장시간이면 먼저 in-progress)\n"
        "- '## 결과' 섹션에 유저에게 보낼 한국어 요약(핵심만, 1500자 이내)을 써라.\n"
        "\n"
        "## 막히면 — 유저에게 직접 묻지 말고 오케에게 물어라 (och.txt §11 왕복)\n"
        "- 결정이 필요해 진행 불가하면 유저에게 직결 금지. ar_ 에 아래로 오케에게 묻고 종료:\n"
        "    [STATUS] needs-info\n"
        "    [QUESTION] <오케가 판단할 한 줄 질문>   (또는 '## 질문' 섹션에 상세)\n"
        "- 오케가 판단(자답 또는 유저 텔레그램 버튼)해 이 지시서 끝에 [ANSWER]/'## 오케 답변' 을\n"
        "  append 하고 워커를 재개시킨다. 재개되면 그 답을 읽고 처음이 아니라 이어서 처리하라.\n"
    )
    a_path.write_text(content, encoding="utf-8")
    return a_path


# ---------- 워커 spawn ----------

def _build_prompt(a_path: Path, resume: bool = False) -> str:
    a_rel = ps.rel_from_repo(a_path)
    seq_m = re.match(r"a_(\d+)_", a_path.name)
    seq = seq_m.group(1) if seq_m else ""
    # 재개(och §11): 이전에 needs-info 로 물었고 오케가 [ANSWER] 를 붙여 다시 띄운 경우.
    resume_note = ""
    if resume or ps.has_pending_answer(a_path):
        resume_note = (
            "★재개(needs-info 왕복): 이전에 네가 오케에게 물어(needs-info) 멈췄고,\n"
            f"   오케의 답이 지시서 {a_rel} 끝의 [ANSWER]/'## 오케 답변' 에 붙어 있다.\n"
            "   처음부터가 아니라 그 답을 반영해 **이어서** 처리하라.\n\n"
        )
    return (
        f"너는 이 프로젝트({_REPO_ROOT})의 자동 워커다.\n\n"
        f"{resume_note}"
        f"1) 지시서를 읽어라: {a_rel}\n"
        "   (헤더 [CHAT_ID]·[PARENT](유저 원문 u_)·[REF_IMAGE] 확인. '## 유저 원문'이 실제 요청이다.)\n"
        "2) 지시서의 '## 지시' 대로 이 프로젝트 코드 컨텍스트로 정제·처리하라.\n"
        "   .claude/rules 와 telegram_bot/orchestrator/och.txt(§4·§7)를 준수한다.\n"
        "3) 결과를 지시서와 같은 폴더에 응답 파일로 남겨라:\n"
        f"   telegram_bot/orchestrator/protocol/a/ar_{seq}_auto.txt\n"
        "   - 첫 줄: [STATUS] done  (실패 시 error|blocked)\n"
        "   - '## 결과' 섹션에 유저에게 보낼 한국어 요약을 써라(1500자 이내).\n"
        "   - 장시간 작업이면 먼저 [STATUS] in-progress 로 만들고, 끝나면 done 으로 바꿔라.\n"
        "   - ★막혀서 결정이 필요하면 유저에게 직결 금지 — [STATUS] needs-info + [QUESTION] 으로\n"
        "     오케에게 물어라(och.txt §11). 오케가 답을 이 지시서에 [ANSWER] 로 붙여 재개시킨다.\n"
        "4) 완료 후 종료하라. 봇이 ar_ 의 종결 STATUS 를 감지해 유저에게 회신한다.\n"
    )


# ---------- 워커→오케 질문 왕복: 재개(och §11) ----------

def find_needs_info() -> list[tuple[Path, Path, str]]:
    """오케 개입 대기 중인 (a_, ar_, 질문) 목록.

    워커가 needs-info 로 멈춘 건들 — 오케(세션)가 자답 또는 유저에게 되묻기 위해 조회.
    이미 [ANSWER] 가 붙어 재개 대기인 것은 제외(중복 처리 방지).
    """
    out: list[tuple[Path, Path, str]] = []
    for a_path, ar_path in ps.find_answered_tasks():
        status = ps.read_response_status(ar_path)
        if not ps.is_needs_info_status(status):
            continue
        if ps.has_pending_answer(a_path):
            continue  # 이미 답 붙음 → resume 대기 (아래 resume_answered 가 처리)
        out.append((a_path, ar_path, ps.read_question(ar_path)))
    return out


def answer_and_resume(a_path: Path, answer: str, source: str = "오케") -> tuple[bool, str]:
    """오케(또는 유저)의 답을 a_ 에 append 하고, ar_ 를 지워 워커를 재개(재spawn).

    - append_answer: 답을 a_ 지시서 끝에 붙여 워커 재개 발판 마련.
    - ar_ 삭제: a_/ar_ 짝이 깨져 '미처리(pending)'로 되돌아감 → 워커가 다시 잡아 이어서 처리.
      (needs-info 였던 ar_ 는 봇이 아카이브하지 않았으므로 여기서 안전히 제거.)
    - mark_dispatched 마커는 남지만, 이 함수가 직접 재spawn 하므로 자동배정과 충돌 없음.
    반환: (성공, 메시지). 봇/세션 루프 보호를 위해 예외를 던지지 않는다.
    """
    if not a_path.exists():
        return (False, "a-not-found")
    ps.append_answer(a_path, answer, source=source)
    # 짝 ar_ 제거(needs-info 응답 폐기) → pending 복귀.
    seq_m = re.match(r"a_(\d+)_(.+)\.txt", a_path.name)
    if seq_m:
        ar = ps.A_DIR / f"ar_{seq_m.group(1)}_{seq_m.group(2)}.txt"
        try:
            ar.unlink()
        except OSError:
            pass
    return spawn_for_task(a_path, resume=True)


def spawn_for_task(a_path: Path, resume: bool = False) -> tuple[bool, str]:
    """a_ 지시서를 처리할 claude -p 워커를 detached spawn.

    반환: (성공, 메시지). 예외를 던지지 않고 (False, 사유) 로 반환(봇 루프 보호).
    """
    if _prune_running() >= MAX_CONCURRENT:
        return (False, f"max-concurrent({MAX_CONCURRENT})")

    cbin = claude_bin()
    if cbin is None:
        return (False, "claude-not-found")

    prompt = _build_prompt(a_path, resume=resume)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = _LOG_DIR / f"worker_{a_path.stem}_{ts}.log"

    cmd = [cbin, "-p", "--dangerously-skip-permissions", prompt]
    try:
        logf = open(log_path, "w", encoding="utf-8")  # noqa: SIM115
        proc = subprocess.Popen(
            cmd,
            cwd=str(_REPO_ROOT),
            stdout=logf,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:  # noqa: BLE001
        return (False, f"spawn-error: {e}")

    _running.append(_Job(proc=proc, a_path=a_path))
    return (True, f"pid={proc.pid} log={ps.rel_from_repo(log_path)}")


# ---------- 배정 오케스트레이션 (봇 루프에서 호출) ----------

def dispatch_pending(on_dispatch=None) -> list[tuple[Path, bool, str]]:
    """미처리 u_ 를 훑어: a_ 지시서 생성 → 워커 spawn (상한 내).

    on_dispatch(u_path, a_path, spawn_msg) — spawn 성공 시 호출(텔레그램 '배정' 피드백용).
    반환: [(u_path, ok, msg), ...] (이번 루프 시도분).

    무손실: spawn 이 상한/일시오류로 실패하면 a_ 를 남기지 않고 되돌려(삭제),
    다음 루프에서 다시 시도한다 → u_ 는 미처리로 유지(유실 없음).
    단 claude-not-found 는 재시도해도 무의미하므로 a_ 는 남겨 세션 워커가 집게 둔다.

    ★게이트(och 제4원칙): ORCH_AUTO_DISPATCH 가 off(기본)면 봇은 u_ 를 워커에 자동 배정하지
      않는다. u_ 는 미처리로 큐에 무손실 보존되고(봇이 저장·접수피드백만 함), 오케 세션이
      §9-0 으로 깨어나 정제→a_ 지시서 작성→배정한다. 이 흐름이 "봇이 u_ 원문 워커 직결"을
      원천 차단한다. on 일 때만 아래 자동 spawn 로직이 동작한다(과도기 호환).
    """
    results: list[tuple[Path, bool, str]] = []
    if not _auto_dispatch_enabled():
        # 자동 dispatch off — u_ 원문을 워커에 직결하지 않는다(오케 경유). 미처리로 보존.
        return results
    for u in find_undispatched():
        if _prune_running() >= MAX_CONCURRENT:
            break

        a_path = build_task_from_user(u)
        if a_path is None:
            results.append((u, False, "task-build-failed"))
            continue

        ok, msg = spawn_for_task(a_path)
        if ok:
            mark_dispatched(u)  # 영속 마킹 → a_ 아카이브 후 재배정 방지(중복 spawn 근본 차단)
            results.append((u, True, msg))
            if on_dispatch is not None:
                try:
                    on_dispatch(u, a_path, msg)
                except Exception:  # noqa: BLE001
                    pass
        else:
            if msg == "claude-not-found":
                # a_ 는 남겨둔다 → 세션 워커(사람 세션)가 pending 으로 집을 수 있음.
                mark_dispatched(u)  # 그래도 자동배정 재시도는 막는다(세션워커가 a_ 를 처리).
                results.append((u, False, msg))
            else:
                # 상한/일시오류 → a_ 되돌려 u_ 를 미처리로 유지(다음 루프 재시도).
                try:
                    a_path.unlink()
                except OSError:
                    pass
                results.append((u, False, msg))
                if msg.startswith("max-concurrent"):
                    break
    return results
