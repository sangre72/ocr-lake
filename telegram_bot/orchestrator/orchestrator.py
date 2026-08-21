"""오케스트레이터 봇 — 파일 중계기 + 자동 워커 배정 (2026-08-05 재설계).

och.txt / protocol/a/README.md 규약 + 유저 지시(2026-08-05):
- 봇은 텔레그램 유저 요청을 protocol/u/u_*.txt 로 저장한다(순수 파이프, 무손실).
- ★재설계: 봇이 새 u_ 를 감지하면 a_ 지시서(맥락 발판)를 만들고 claude -p 워커를 spawn 해
  직접 처리를 배정한다(worker.py). "세션 깨움" 방식(§9-0)을 이 자동배정으로 대체.
  - u_ → a_ 로 변환(맥락 발판) 후 워커가 a_ 를 읽어 프로젝트 컨텍스트로 처리 → ar_ 응답.
  - 봇이 ar_ 종결 STATUS 를 감지해 유저에게 회신(relay_worker_responses, 기존 유지).
- 접수 피드백(u_ 저장 시) + 배정 피드백(a_ 생성·워커 spawn 시) 텔레그램 발신.

흐름:
  텔레그램 → u_{NN}.txt 저장 (+ "접수" 피드백)
          → [봇 5초 루프] 미처리 u_ 감지 → a_{NN}_auto.txt 생성 + 워커 spawn (+ "배정" 피드백)
          → 워커(claude -p, cwd=repo)가 처리 → ar_{NN}_auto.txt 작성
  텔레그램 ← ar_{NN}.txt 종결 감지 → 회신 (봇 5초 폴링)

무손실·안죽음(och.txt 제2원칙): spawn 실패·claude 미설치 등은 worker.py 가 (False,사유)로
반환하고 봇 루프는 try/except 로 감싸 절대 죽지 않는다. u_ 는 항상 먼저 저장(유실 0).

실행:  cd python-server && uv run python -m telegram_bot.orchestrator.orchestrator
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from . import protocol_store as ps
from . import worker as wk
from .telegram_io import TelegramIO

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parents[2]  # repo 루트 자동도출(프로젝트 불문)

# 캡션 없이 사진만 온 경우, 같은 chat 의 다음 텍스트를 이 SEQ 에 연결하기 위한 임시 보관.
# (모듈 변수 — 봇 재시작 시 소실. 순간적 "사진→텍스트" 연결용이라 영속 불필요.)
_PENDING_IMAGE_SEQ: dict[int, int] = {}

# ---------- 오케 세션 생존 감시 (och 제2·제5원칙 — C, 2026-08-05) ----------
# 오케(Claude Code 세션)는 살아있는 동안 이 파일 mtime 을 갱신한다. 제5원칙(loop) 전환 후
# 갱신 주체는 오케의 /loop 틱(`date > logs/.orch_alive`)이다 — loop 이 돌면 세션 생존.
# 봇(상시 프로세스)이 mtime 을 관찰해 오래 끊기면(=loop 멈춤=세션 죽음) 유저에게 1회 경보한다.
# harness 특성상 봇이 세션을 재기동할 수는 없으므로 '경보 + 큐 무손실 보존'이 정공법이다:
#   실작업 u_ 는 봇이 자동배정해 오케 없이도 처리되고(B),
#   오케 전용 신호(버튼답변·needs-info 답)만 오케 부활을 기다리며 큐에 무손실 보존된다(제2원칙).
_ORCH_ALIVE_FILE = _REPO_ROOT / "logs" / ".orch_alive"
# 이 시간(초) 넘게 생존신호가 끊기면 오케가 죽은 것으로 간주. 기본 5분.
_ORCH_ALIVE_TIMEOUT = int(os.environ.get("ORCH_ALIVE_TIMEOUT_SEC", "300"))
# 경보 재발송 최소 간격(초) — 죽어있는 동안 스팸 방지. 기본 30분.
_ORCH_ALERT_INTERVAL = int(os.environ.get("ORCH_ALIVE_ALERT_INTERVAL_SEC", "1800"))
# 마지막 경보 발송 시각(모듈 변수). 0 = 아직 미발송(또는 오케 생존 중 리셋됨).
_orch_alert_sent_at: float = 0.0

# ---------- 응답지연 감지 (a_224, 2026-08-07) ----------
# check_orch_alive 는 '세션 죽음'(생존신호 끊김)을 잡지만, 20분 loop 틱마다 신호가 갱신돼
# "감시는 도는데 Claude 응답만 멈춘" 케이스는 못 잡는다. → 미처리 u_ 가 오래 방치되면
# = 응답 지연으로 보고, 정상→지연 진입 시 1회 경보 + 지연→정상 복구 시 1회 정상화(에지 트리거).
# 미처리 u_ 판정은 worker.find_undispatched()(seen·orch_only·seed·hold·a_ 존재 제외) 재사용 →
# 오케 seen 판정과 정합(오케가 처리한 u_ 를 미처리로 오판하지 않음).
_REPLY_DELAY_SEC = int(os.environ.get("ORCH_REPLY_DELAY_SEC", "300"))  # 미처리 u_ 이 초 넘게 방치=지연. 기본 5분.
# 응답지연 경보를 이미 보냈는지(상태 전이 에지 보장 — 지연 지속 중 재발송 금지). True=경보 발송됨.
_reply_delay_alerted: bool = False


def _load_env() -> None:
    """orchestrator/.env 를 os.environ 에 로드 (python-dotenv 없이)."""
    env_path = _HERE / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


# ---------- 자동 워커 배정 ----------

def _dispatch_feedback(tg: TelegramIO, u_path: Path, a_path: Path, spawn_msg: str) -> None:
    """워커 배정(a_ 생성 + spawn) 성공 시 유저에게 '배정' 피드백을 보낸다.

    on_dispatch 콜백 — worker.dispatch_pending 에서 호출. 실패해도 봇을 막지 않는다.
    """
    chat_raw = ps.read_field(u_path, "CHAT_ID")
    if not chat_raw.isdigit():
        return
    title = ps.read_field(a_path, "TITLE") or a_path.stem
    try:
        tg.send_message(
            int(chat_raw),
            f"🛠 작업을 배정했습니다 ({a_path.stem}).\n요청: {title}\n워커가 처리 중입니다 — 완료되면 알려드릴게요.",
        )
    except Exception as e:  # noqa: BLE001
        print(f"[경고] 배정 피드백 발신 실패: {e}")


def dispatch_new_requests(tg: TelegramIO) -> None:
    """미처리 u_ → a_ 지시서 생성 + 워커 spawn. 예외를 삼켜 봇 루프를 보호한다."""
    try:
        results = wk.dispatch_pending(
            on_dispatch=lambda u, a, msg: _dispatch_feedback(tg, u, a, msg)
        )
    except Exception as e:  # noqa: BLE001
        print(f"[경고] 워커 배정 루프 실패(무시하고 계속): {e}")
        return
    for u_path, ok, msg in results:
        if ok:
            print(f"[배정→워커] {u_path.name} → a_ 생성·spawn {msg}")
        elif msg == "claude-not-found":
            print(f"[배정보류] {u_path.name}: claude 미설치 — a_ 는 남겨 세션워커가 집게 함")
        elif msg.startswith("max-concurrent"):
            print(f"[배정대기] {u_path.name}: 동시 워커 상한 도달 — 다음 루프 재시도")
        else:
            print(f"[배정실패] {u_path.name}: {msg} — 다음 루프 재시도")


def _orch_alert_targets(allowed_ids: set[int]) -> list[int]:
    """오케 사망 경보를 보낼 chat_id 목록.

    - 운영자 화이트리스트(TELEGRAM_ALLOWED_CHAT_IDS)가 있으면 그들에게.
    - 없으면 미처리 u_ 중 가장 최근 것의 CHAT_ID 로 폴백(요청자에게 상황 통지).
    """
    if allowed_ids:
        return sorted(allowed_ids)
    latest: tuple[str, int] | None = None
    for u in ps.U_DIR.glob("u_*.txt"):
        raw = ps.read_field(u, "CHAT_ID")
        if raw.isdigit():
            if latest is None or u.name > latest[0]:
                latest = (u.name, int(raw))
    return [latest[1]] if latest else []


def check_orch_alive(tg: TelegramIO, allowed_ids: set[int]) -> None:
    """오케 세션 생존신호(logs/.orch_alive mtime)를 관찰해 끊기면 1회 경보(제2원칙 — C).

    - 신호가 살아있거나 파일이 없으면(오케가 아직 안 띄운 초기 상태 포함) 경보 안 함 → 오탐 방지.
    - 끊긴 지 _ORCH_ALIVE_TIMEOUT 초 초과 + 마지막 경보 후 _ORCH_ALERT_INTERVAL 경과 시에만 발송(스팸 방지).
    - 오케가 되살아나면(신호 갱신) _orch_alert_sent_at 을 리셋해 다음 사망 시 다시 알린다.
    봇 루프에서 매 틱 호출. 예외는 삼켜 루프를 막지 않는다.
    """
    global _orch_alert_sent_at
    try:
        if not _ORCH_ALIVE_FILE.exists():
            return  # 컨벤션 미도입/오케 미기동 — 오탐 금지(경보하지 않음)
        age = time.time() - _ORCH_ALIVE_FILE.stat().st_mtime
        now = time.monotonic()
        if age <= _ORCH_ALIVE_TIMEOUT:
            # 오케 생존 — 경보 상태 리셋(다음 사망 시 즉시 알릴 수 있게).
            _orch_alert_sent_at = 0.0
            return
        # 죽은 것으로 간주 — 스팸 방지 간격 확인.
        if _orch_alert_sent_at and (now - _orch_alert_sent_at) < _ORCH_ALERT_INTERVAL:
            return
        targets = _orch_alert_targets(allowed_ids)
        if not targets:
            print(f"[경고] 오케 생존신호 {int(age)}s 끊김 — 경보 대상 chat 없음(큐는 보존).")
            _orch_alert_sent_at = now
            return
        msg = (
            "🔴 오케스트레이터 세션이 응답하지 않습니다.\n"
            f"(생존신호가 약 {int(age // 60)}분 끊김)\n\n"
            "요청은 큐에 안전히 보관돼 유실되지 않습니다. "
            "오케 세션을 다시 띄우면 그동안 쌓인 요청을 이어서 처리합니다."
        )
        for cid in targets:
            try:
                tg.send_message(cid, msg)
            except Exception as e:  # noqa: BLE001
                print(f"[경고] 오케 사망 경보 발신 실패(chat {cid}): {e}")
        _orch_alert_sent_at = now
        print(f"[오케사망경보] 생존신호 {int(age)}s 끊김 — {len(targets)}개 chat 통지.")
    except Exception as e:  # noqa: BLE001
        print(f"[경고] 오케 생존 감시 실패(무시): {e}")


def check_reply_delay(tg: TelegramIO, allowed_ids: set[int]) -> None:
    """응답지연 상태 전이 경보 (a_224 — Claude 무응답 대비). 정확히 1회씩.

    - 미처리 u_(worker.find_undispatched — seen/orch_only/seed/hold/a_ 제외) 중 가장 오래된 것의
      mtime 경과 > _REPLY_DELAY_SEC 면 '응답지연' 상태로 본다.
    - 정상→지연 진입 시 1회만 경보(_reply_delay_alerted True). 지연 지속 중 재발송 금지.
    - 지연→정상(미처리 u_ 해소=오케 처리) 전이 시 1회 정상화 + 플래그 리셋.
    - 미처리 u_ 없으면 정상(오탐 방지). 예외 삼켜 봇 루프 보호(제2원칙).
    """
    global _reply_delay_alerted
    try:
        pending = wk.find_undispatched()
        now = time.time()
        # 가장 오래된 미처리 u_ 의 방치 경과(초). 없으면 0(=정상).
        oldest_age = 0.0
        if pending:
            oldest_age = max(now - u.stat().st_mtime for u in pending)
        is_delayed = oldest_age > _REPLY_DELAY_SEC

        if is_delayed and not _reply_delay_alerted:
            # 정상→지연 진입: 경보 1회.
            targets = _orch_alert_targets(allowed_ids)
            msg = (
                "⏳ 처리가 지연되고 있습니다 (서비스 점검/응답 지연 가능).\n"
                "요청은 안전하게 큐에 보존됩니다 — 복구되면 이어서 처리해 알려드릴게요."
            )
            for cid in targets:
                try:
                    tg.send_message(cid, msg)
                except Exception as e:  # noqa: BLE001
                    print(f"[경고] 응답지연 경보 발신 실패(chat {cid}): {e}")
            _reply_delay_alerted = True
            print(f"[응답지연경보] 미처리 u_ {int(oldest_age)}s 방치 — {len(targets)}개 chat 통지.")
        elif not is_delayed and _reply_delay_alerted:
            # 지연→정상 복구: 정상화 1회 + 리셋.
            targets = _orch_alert_targets(allowed_ids)
            msg = "✅ 정상 복구됐습니다. 밀린 요청을 처리했습니다."
            for cid in targets:
                try:
                    tg.send_message(cid, msg)
                except Exception as e:  # noqa: BLE001
                    print(f"[경고] 응답지연 정상화 발신 실패(chat {cid}): {e}")
            _reply_delay_alerted = False
            print("[응답지연복구] 미처리 u_ 해소 — 정상화 통지.")
    except Exception as e:  # noqa: BLE001
        print(f"[경고] 응답지연 감시 실패(무시): {e}")


# ---------- 메인 루프 ----------

def run() -> None:
    _load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN 이 .env 에 없습니다.")

    allowed = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    allowed_ids = {int(x) for x in allowed.split(",") if x.strip().isdigit()}

    # getUpdates long-poll timeout = 모니터링 주기(기본 5초). 이 시간마다 루프가 돌며
    # (a) ar_*.txt 응답 회신, (b) 미처리 u_ 워커 배정을 함께 처리한다.
    poll = int(os.environ.get("ORCH_POLL_INTERVAL", "5"))
    tg = TelegramIO(token, timeout=poll)
    me = tg.get_me()
    print(f"[오케스트레이터] 봇 연결됨: @{me.get('username')} (id={me.get('id')})")

    # 도입 시점의 과거 u_ 를 한꺼번에 배정하지 않도록 최초 1회 seed.
    try:
        seeded = wk.seed_existing_if_needed()
        if seeded:
            print(f"[초기화] 과거 u_ {seeded}건을 '처리됨'으로 seed (신규만 자동배정).")
    except Exception as e:  # noqa: BLE001
        print(f"[경고] seed 실패(무시): {e}")

    # 봇 종료 시 실행 중 자동워커를 고아로 남기지 않도록 그레이스풀 셧다운 훅 설치(och 제2원칙).
    try:
        wk.install_shutdown_hooks()
    except Exception as e:  # noqa: BLE001
        print(f"[경고] 셧다운 훅 설치 실패(무시): {e}")

    cbin = wk.claude_bin()
    if cbin:
        print(
            f"[자동워커] 활성 — claude={cbin}, 동시상한={wk.MAX_CONCURRENT}, "
            f"타임아웃={wk.WORKER_TIMEOUT}s"
        )
    else:
        print("[자동워커] claude 미탐지 — a_ 지시서는 만들되 spawn 은 생략(세션워커가 집음).")
    print(f"[오케스트레이터] 폴링 주기 {poll}s. 봇=파이프, 워커=claude -p 자동배정.")

    offset: int | None = None
    while True:
        # (a0) 매 루프 실행 중 워커 정리 — 죽은 자식 명시적 reap(<defunct> 방지) +
        #      멈춘(신호 끊긴) 워커 타임아웃 정리(och 제2원칙). 유휴 시에도 반드시 돈다.
        try:
            wk.running_count()
        except Exception as e:  # noqa: BLE001
            print(f"[경고] 워커 정리(prune) 실패(무시): {e}")

        # (a) worker 가 완료한 ar_*.txt → 유저에게 회신
        try:
            relay_worker_responses(tg)
        except Exception as e:  # noqa: BLE001
            print(f"[경고] 워커 응답 회신 실패: {e}")

        # (a2) 미처리 u_ → a_ 지시서 + 워커 spawn 배정 (예외는 내부에서 삼킴)
        #      단, '오케 전용 신호'(버튼답변)로 마킹된 u_ 는 자동배정에서 제외됨(B, 제4원칙).
        dispatch_new_requests(tg)

        # (a3) 오케 세션 생존 감시 — 신호 끊기면 유저에게 1회 경보(C, 제2원칙). 큐는 무손실 보존.
        #      오케(세션)가 /loop 틱마다 logs/.orch_alive 를 갱신한다(제5원칙). loop 이 멈추면
        #      (세션 죽음) 봇이 이를 감지해 유저에게 "세션 다시 띄워달라" 1회 경보한다.
        check_orch_alive(tg, allowed_ids)

        # (a4) 응답지연 감지(a_224) — 미처리 u_ 가 오래 방치되면(세션 살아도 Claude 응답만 멈춤)
        #      유저에게 1회 경보 + 복구 시 1회 정상화. check_orch_alive(세션 죽음)와 공존하는 별개 층.
        check_reply_delay(tg, allowed_ids)

        # (b) 텔레그램 신규 업데이트 수신 (long-poll). message + callback_query 를 함께 받아
        #     ask| 버튼 콜백을 동일 폴러에서 처리한다(getUpdates offset 경합 방지).
        try:
            updates = tg.get_updates(
                offset=offset, allowed_updates=["message", "callback_query"]
            )
        except Exception as e:  # noqa: BLE001
            print(f"[경고] getUpdates 실패: {e}. 3초 후 재시도.")
            time.sleep(3)
            continue

        for upd in updates:
            # offset 은 try 밖에서 먼저 전진 — 어떤 예외가 나도 같은 (문제)업데이트를 무한
            # 재처리하지 않게 한다(진행 보장). 개별 업데이트 처리 실패는 아래 try 가 삼킨다.
            offset = upd["update_id"] + 1

            # ★업데이트 1건 처리 전체를 try 로 감싼다(제2원칙 — 봇 안 죽음): 악성/기형 업데이트나
            #   handle_* 예외로 메인루프가 죽지 않도록 삼키고 다음 업데이트로 넘어간다.
            try:
                _process_update(tg, upd, allowed_ids)
            except Exception as e:  # noqa: BLE001
                print(f"[경고] 업데이트 처리 실패(무시하고 계속): {e}")


def _process_update(tg: TelegramIO, upd: dict, allowed_ids: set[int]) -> None:
    """텔레그램 업데이트 1건 처리(메시지·사진·콜백). 예외는 호출부(run 루프)가 삼킨다."""
    # 인라인 버튼 클릭(callback_query) 처리.
    cq = upd.get("callback_query")
    if cq is not None:
        data = (cq.get("data") or "")
        try:
            if data.startswith("ask|"):
                # 오케 → 유저 버튼 질문의 답. u_ 로 남겨 오케가 읽는다.
                _handle_ask_callback(tg, cq)
            else:
                try:
                    tg.answer_callback_query(cq.get("id"))
                except Exception:  # noqa: BLE001
                    pass
        except Exception as e:  # noqa: BLE001
            print(f"[경고] 콜백 처리 실패: {e}")
        return

    msg = upd.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    username = (msg.get("from") or {}).get("username", "")
    if not chat_id:
        return
    if allowed_ids and chat_id not in allowed_ids:
        tg.send_message(chat_id, "허용되지 않은 사용자입니다.")
        return

    # 사진(photo) 또는 이미지 문서(document) → 참조 이미지 수신 처리
    file_ref = _extract_image_file(msg)
    if file_ref is not None:
        file_id, ext = file_ref
        caption = msg.get("caption", "") or ""
        handle_photo(tg, chat_id, username, file_id, ext, caption)
        return

    text = msg.get("text", "")
    if not text:
        return
    handle_message(tg, chat_id, username, text)


def _handle_ask_callback(tg: TelegramIO, cq: dict) -> None:
    """오케(세션) → 유저 버튼 질문의 답 처리.

    callback_data: "ask|{key}|{value}"  (오케가 telegram_bot/orchestrator/scripts/ask_telegram.py 로 발송)
    - 유저에게 즉시 토스트 + 버튼 제거.
    - 답을 u_*.txt 로 남겨 오케가 읽고 반영(봇은 u_ 기록만, a_ 생성은 오케 몫).
    """
    data = cq.get("data") or ""
    msg = cq.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    username = (cq.get("from") or {}).get("username", "")
    q_text = (msg.get("text") or "").strip()

    parts = data.split("|")
    key = parts[1] if len(parts) > 1 else ""
    value = parts[2] if len(parts) > 2 else ""

    # 선택한 버튼 라벨 찾기(있으면 사람이 읽기 좋게)
    label = value
    for row in (msg.get("reply_markup") or {}).get("inline_keyboard", []):
        for btn in row:
            if btn.get("callback_data") == data:
                label = btn.get("text", value)

    try:
        tg.answer_callback_query(cq.get("id"), text=f"✅ {label}")
    except Exception:  # noqa: BLE001
        pass
    # 버튼 제거(중복 클릭 방지)
    if chat_id and message_id:
        try:
            tg.edit_message_reply_markup(chat_id, message_id, inline_keyboard=None)
        except Exception:  # noqa: BLE001
            pass

    # u_ 로 답 기록 → 오케가 읽음
    # ★이 u_ 는 '오케 전용 신호'(워커 실작업 아님) — 봇 자동배정에서 제외(제4원칙, u_144 사고 방지).
    try:
        seq = ps.next_seq()
        req = (
            f"[버튼답변] 질문키={key} 선택={value} ({label})\n"
            f"원질문: {q_text}"
        )
        u_path = ps.write_user_request(chat_id, username or "ask-reply", req, seq)
        wk.mark_orch_only(u_path)
        print(f"[콜백→u_{seq:02d}] 버튼답 {key}={value} (오케전용, 자동배정 제외)")
    except Exception as e:  # noqa: BLE001
        print(f"[경고] 버튼답 u_ 기록 실패: {e}")




def handle_message(tg: TelegramIO, chat_id: int, username: str, text: str) -> None:
    """유저 메시지 1건 → u_ 파일로 저장 (+ 접수 피드백). 배정은 봇 루프가 담당."""
    print(f"[수신] chat={chat_id} @{username}: {text[:60]}")

    if text.strip() in ("/start", "/help"):
        tg.send_message(
            chat_id,
            "안녕하세요! ocr-lake 오케스트레이터입니다.\n"
            "요청을 워커에게 전달하고 결과를 알려드립니다. "
            "무엇을 도와드릴까요?",
        )
        return

    # 직전에 캡션 없이 사진만 온 경우 → 이 텍스트를 그 SEQ 에 이어붙인다(같은 요청으로 묶음).
    pending_seq = _PENDING_IMAGE_SEQ.pop(chat_id, None)
    if pending_seq is not None:
        u_path = ps.find_user_file(pending_seq)
        if u_path is not None:
            content = u_path.read_text(encoding="utf-8")
            # 원문 섹션에 텍스트를 채워 넣는다 (사진 접수 시 비어 있던 부분).
            if content.rstrip().endswith("## 원문"):
                content = content.rstrip() + f"\n{text}\n"
            else:
                content = content.rstrip() + f"\n{text}\n"
            u_path.write_text(content, encoding="utf-8")
            # 사진 접수 시 걸어둔 배정 보류 해제 → 다음 루프에서 이 u_ 가 자동배정된다.
            try:
                wk.release_dispatch(u_path)
            except Exception:  # noqa: BLE001
                pass
            tg.send_message(
                chat_id,
                f"✅ 이미지(#{pending_seq:02d})와 함께 요청을 접수했습니다. 곧 워커에 배정합니다.",
            )
            print(f"[수신→u_{pending_seq:02d}] 대기 이미지에 텍스트 연결")
            return

    seq = ps.next_seq()
    # 봇은 유저 원문을 u_*.txt 에 저장한다(무손실). 워커 배정(a_ 생성 + spawn)은
    # 봇 5초 루프의 dispatch_new_requests() 가 담당한다(맥락 발판 a_ 경유).
    ps.write_user_request(chat_id, username, text, seq)
    tg.send_message(
        chat_id,
        f"✅ 접수했습니다 (#{seq:02d}). 곧 워커에 배정해 진행하겠습니다.",
    )
    print(f"[수신→u_{seq:02d}] 저장 완료 — 다음 루프에서 자동배정")


# ---------- 사진(참조 이미지) 수신 ----------

def _extract_image_file(msg: dict) -> tuple[str, str] | None:
    """message 에서 이미지 파일 참조를 뽑는다.

    반환: (file_id, ext) | None
      - photo: 가장 큰 사이즈(마지막 항목) 선택, ext=jpg.
      - document: image/* mime 만 허용. ext 는 mime 서브타입 또는 파일명 확장자.
    """
    photos = msg.get("photo") or []
    if photos:
        # 텔레그램 photo 배열은 작은→큰 순. 마지막이 최대 해상도.
        largest = photos[-1]
        fid = largest.get("file_id")
        if fid:
            return (fid, "jpg")

    doc = msg.get("document") or {}
    mime = (doc.get("mime_type") or "").lower()
    if doc.get("file_id") and mime.startswith("image/"):
        subtype = mime.split("/", 1)[1] if "/" in mime else "jpg"
        ext = "jpg" if subtype in ("jpeg", "jpg") else subtype
        return (doc["file_id"], ext)
    return None


def handle_photo(
    tg: TelegramIO, chat_id: int, username: str,
    file_id: str, ext: str, caption: str,
) -> None:
    """수신 사진 → protocol/refs/ 저장 + u_ 파일 기록. 배정은 봇 루프가 담당."""
    print(f"[사진수신] chat={chat_id} @{username} file={file_id[:8]} caption={caption[:40]!r}")

    seq = ps.next_seq()
    dest = ps.ref_dest_path(seq, file_id, ext)
    try:
        info = tg.get_file(file_id)
        remote_path = info.get("file_path", "")
        if not remote_path:
            tg.send_message(chat_id, "⚠️ 이미지 정보를 가져오지 못했습니다. 다시 보내주세요.")
            return
        tg.download_file(remote_path, dest)
    except Exception as e:  # noqa: BLE001
        print(f"[경고] 이미지 다운로드 실패: {e}")
        tg.send_message(chat_id, "⚠️ 이미지 다운로드에 실패했습니다. 다시 보내주세요.")
        return

    ref_rel = ps.rel_from_repo(dest)
    ps.write_user_image_request(chat_id, username, caption, ref_rel, seq)

    if caption.strip():
        tg.send_message(
            chat_id,
            f"🖼 이미지 접수 (#{seq:02d}) — 곧 워커에 배정합니다.",
        )
        print(f"[사진→u_{seq:02d}] 캡션 포함 접수")
    else:
        # 캡션이 없으면 다음 텍스트를 이 SEQ 에 연결하도록 보관.
        # 배정을 미루기 위해 seed 마커를 임시로 찍어(다음 텍스트 도착 전 조기배정 방지),
        # 텍스트가 붙으면 handle_message 가 마커를 제거한다.
        _PENDING_IMAGE_SEQ[chat_id] = seq
        try:
            wk.hold_dispatch(ps.find_user_file(seq))
        except Exception:  # noqa: BLE001
            pass
        tg.send_message(
            chat_id,
            f"🖼 이미지 접수 (#{seq:02d}) — 곧 워커가 OCR로 텍스트를 추출합니다.\n"
            "구조화(영수증·명함 등) 등 추가 요청이 있으면 텍스트로 이어서 보내주세요(없으면 잠시 후 자동 처리).",
        )
        print(f"[사진→u_{seq:02d}] 캡션 없음 — 텍스트 대기(배정 보류)")


def relay_worker_responses(tg: TelegramIO) -> None:
    """worker 가 작성한 ar_*.txt 를 찾아 유저에게 회신하고 아카이브.

    규약 (2026-08-05 수정 — 워커→오케 질문 왕복 프로토콜, och §11):
    - in-progress / in_progress / 동의어 → 아카이브 금지 (하트비트 대기)
    - needs-info / waiting-answer → ★유저 직결 금지·아카이브 금지.
      워커가 오케에게 물은 것 → 오케(세션)가 검토해 자답하거나 유저에게 정제해 되묻는다(제4원칙).
      봇은 회신·아카이브하지 않고 오케 개입 대기 상태로 남긴다(로그로만 표시).
    - 종결 상태(done|error|blocked|failed) 만 회신 후 아카이브
    - 알 수 없는 status → 아카이브하지 않고 경고만 (미완 작업 보호)
    """
    for a_path, ar_path in ps.find_answered_tasks():
        status = ps.read_response_status(ar_path)

        # 진행 중: 어떤 경우에도 아카이브 금지 (하트비트 갱신 대기)
        if ps.is_in_progress_status(status):
            continue

        # ★needs-info: 워커→오케 질문. 유저 직결·아카이브 금지 — 오케 경유(제4원칙).
        #   오케 세션이 5초 폴링으로 이 상태를 포착 → 자답 또는 유저에게 텔레그램 정제질문 →
        #   a_ 에 [ANSWER] append → ar_ 삭제(재spawn) 로 워커 재개. 봇은 건드리지 않는다.
        if ps.is_needs_info_status(status):
            print(f"[질문대기] {ar_path.name} — 오케 개입 대기(needs-info, 아카이브 보류)")
            continue

        # 종결이 아니면(unknown 등) 보호 — 예전에 else 로 떨어져 오아카이브됨
        if not ps.is_terminal_status(status):
            print(
                f"[경고] 비종결 status={status!r} — 아카이브 보류: {ar_path.name}"
            )
            continue

        chat_id_raw = ps.read_field(a_path, "CHAT_ID")
        summary = ps.summarize_response(ar_path)

        if chat_id_raw.isdigit():
            chat_id = int(chat_id_raw)
            if status == "done":
                tg.send_message(chat_id, f"🎬 완료 ({a_path.stem})\n\n{summary}")
            else:  # error | blocked | failed
                tg.send_message(chat_id, f"⚠️ 처리 {status}\n\n{summary}")
            print(f"[회신] {ar_path.name} → chat {chat_id} ({status})")
        else:
            # 회신 대상 불명이어도 종결건은 아카이브(큐 정체 방지). 진행 중은 위에서 이미 제외.
            print(f"[경고] CHAT_ID 없음 — 회신 생략 후 아카이브: {ar_path.name} ({status})")

        ps.archive(a_path, ar_path)


if __name__ == "__main__":
    run()
