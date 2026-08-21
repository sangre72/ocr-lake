"""파일 기반 프로토콜 저장소 (telegram_bot/orchestrator/protocol/ 로 응집 — u_136).

och.txt / protocol/a/README.md 규약:
- 유저 요청:  protocol/u/u_{NN}_{topic}.txt        (봇이 저장)
- 워커 지시:  protocol/a/a_{NN}_{topic}.txt        (봇=오케스트레이터가 작성)
- 워커 응답:  protocol/a/ar_{NN}_{topic}.txt       (worker_1 세션이 작성)
- 지시/응답은 같은 번호 NN 으로 짝. ar_ 없는 a_ = 미처리.

봇은 헤드리스 LLM 을 호출하지 않는다. 순수 파일 중계기.

경로(2026-08-05 u_136 이동): 큐는 이 파일과 같은 디렉토리 아래 protocol/ 로 응집한다.
(this file: <repo>/telegram_bot/orchestrator/protocol_store.py)
- parents[0] = telegram_bot/orchestrator  → 여기 아래 protocol/ 가 실제 큐.
- parents[2] = repo 루트(자동도출, 프로젝트 불문) → u_ 파일에 기록할 상대경로 계산·hint 용.
"""

from __future__ import annotations

import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # telegram_bot/orchestrator
_REPO_ROOT = Path(__file__).resolve().parents[2]  # repo 루트(자동도출, 프로젝트 불문) — 상대경로 계산용
# 큐 응집 위치: telegram_bot/orchestrator/protocol/ (파이프 자산을 telegram_bot 안으로 — u_136)
PROTOCOL_DIR = _HERE / "protocol"
U_DIR = PROTOCOL_DIR / "u"
A_DIR = PROTOCOL_DIR / "a"
DONE_DIR = PROTOCOL_DIR / "done"
# 완료 확인된 지시/응답의 최종 아카이브 (봇 미감시·git 미추적 — 유저 지시 2026-08-01).
# done 을 여기로 이관해도 next_seq 가 이 디렉토리를 집계해 번호 재사용을 막는다.
ARCHIVE_DIR = PROTOCOL_DIR / "archive"
# 텔레그램 수신 참조 이미지 (런타임 데이터 — .gitignore 대상)
REFS_DIR = PROTOCOL_DIR / "refs"

for _d in (U_DIR, A_DIR, DONE_DIR, ARCHIVE_DIR, REFS_DIR):
    _d.mkdir(parents=True, exist_ok=True)



def _slug(text: str, limit: int = 24) -> str:
    """토픽 슬러그: 공백→_, 특수문자 제거, 한글/영문/숫자만."""
    s = re.sub(r"[^\w가-힣]+", "_", text.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:limit] or "task")


def next_seq() -> int:
    """다음 SEQ 번호 — a_/u_/done 의 최대 NN + 1.

    u_ 도 함께 집계한다: 오케스트레이터가 a_ 를 만들기 전에 유저 요청(u_)이
    연속으로 들어와도 같은 번호로 덮어쓰지 않도록(특히 사진 접수) 보장한다.
    """
    nums = []
    for d, pat in (
        (A_DIR, "a_*.txt"),
        (DONE_DIR, "a_*.txt"),
        (ARCHIVE_DIR, "a_*.txt"),  # 완료 아카이브도 집계 → 번호 재사용 방지
        (U_DIR, "u_*.txt"),
    ):
        for p in d.glob(pat):
            m = re.match(r"[au]_(\d+)_", p.name)
            if m:
                nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


# ---------- 유저 요청 (u_{NN}_{topic}.txt) ----------

def write_user_request(chat_id: int, username: str, text: str, seq: int) -> Path:
    topic = _slug(text)
    path = U_DIR / f"u_{seq:02d}_{topic}.txt"
    content = (
        f"[FROM] user\n"
        f"[CHAT_ID] {chat_id}\n"
        f"[USERNAME] {username}\n"
        f"[SEQ] {seq:02d}\n\n"
        "## 원문\n"
        f"{text}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


# ---------- 참조 이미지 수신 (protocol/refs/) ----------

def ref_dest_path(seq: int, file_id: str, ext: str = "jpg") -> Path:
    """수신 이미지 저장 경로 — ref_{NN}_{file_id 앞8자}.{ext}."""
    fid8 = re.sub(r"[^A-Za-z0-9]+", "", file_id)[:8] or "img"
    ext = re.sub(r"[^a-z0-9]+", "", ext.lower()) or "jpg"
    return REFS_DIR / f"ref_{seq:02d}_{fid8}.{ext}"


def rel_from_repo(path: Path) -> str:
    """repo 루트 기준 상대경로 (u_ 파일에 기록용, POSIX 슬래시)."""
    try:
        return path.resolve().relative_to(_REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def write_user_image_request(
    chat_id: int, username: str, caption: str, ref_rel: str, seq: int
) -> Path:
    """사진(+선택 캡션) 요청 → u_{NN}.txt 작성.

    [REF_IMAGE] 필드에 repo 상대경로를, 원문에는 caption 을 저장한다.
    caption 이 비면 토픽은 'image_ref' 로 대체한다.
    """
    topic = _slug(caption) if caption.strip() else "image_ref"
    path = U_DIR / f"u_{seq:02d}_{topic}.txt"
    content = (
        f"[FROM] user\n"
        f"[CHAT_ID] {chat_id}\n"
        f"[USERNAME] {username}\n"
        f"[SEQ] {seq:02d}\n"
        f"[REF_IMAGE] {ref_rel}\n\n"
        "## 원문\n"
        f"{caption}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def find_user_file(seq: int) -> Path | None:
    """SEQ 로 u_{NN}_*.txt 파일 1건을 찾는다 (없으면 None)."""
    for p in U_DIR.glob(f"u_{seq:02d}_*.txt"):
        return p
    return None


def append_ref_to_user(path: Path, ref_rel: str) -> None:
    """기존 u_ 파일에 [REF_IMAGE] 필드를 추가(이미 있으면 다중 라인으로 누적)한다."""
    text = path.read_text(encoding="utf-8")
    line = f"[REF_IMAGE] {ref_rel}"
    if line in text:
        return
    # 헤더 블록(빈 줄 앞)에 삽입. 없으면 맨 위 append.
    if "\n\n" in text:
        head, rest = text.split("\n\n", 1)
        text = f"{head}\n{line}\n\n{rest}"
    else:
        text = f"{line}\n{text}"
    path.write_text(text, encoding="utf-8")


# ---------- 워커 지시 (a_{NN}_{topic}.txt) ----------

def write_worker_task(
    chat_id: int,
    topic: str,
    instruction: str,
    seq: int,
    task_type: str = "research",
    scope: str = "",
    constraints: str = "",
    priority: str = "normal",
) -> Path:
    """루트 protocol/a 규약대로 워커 지시서를 작성한다.

    [CHAT_ID] 는 봇이 응답(ar_)을 회신할 대상 식별용 (규약 확장 필드).
    """
    path = A_DIR / f"a_{seq:02d}_{_slug(topic)}.txt"
    content = (
        f"[TYPE] {task_type}\n"
        f"[PRIORITY] {priority}\n"
        f"[TITLE] {topic}\n"
        f"[CHAT_ID] {chat_id}\n\n"
        "## 지시\n"
        f"{instruction}\n\n"
        "## 파일/범위\n"
        f"{scope or '(자유)'}\n\n"
        "## 제약\n"
        f"{constraints or '(없음)'}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


# ---------- 응답 (ar_{NN}_{topic}.txt) — worker_1 이 작성, 봇은 읽기만 ----------

def find_pending_tasks() -> list[Path]:
    """대응 ar_*.txt 가 없는 a_*.txt (아직 워커가 안 잡은 지시)."""
    out = []
    for a in sorted(A_DIR.glob("a_*.txt")):
        m = re.match(r"a_(\d+)_(.+)\.txt", a.name)
        if not m:
            continue
        if not (A_DIR / f"ar_{m.group(1)}_{m.group(2)}.txt").exists():
            out.append(a)
    return out


def find_answered_tasks() -> list[tuple[Path, Path]]:
    """(a_*.txt, ar_*.txt) 짝이 맞고 아직 회신 안 한(=아카이브 전) 것들."""
    out = []
    for a in sorted(A_DIR.glob("a_*.txt")):
        m = re.match(r"a_(\d+)_(.+)\.txt", a.name)
        if not m:
            continue
        ar = A_DIR / f"ar_{m.group(1)}_{m.group(2)}.txt"
        if ar.exists():
            out.append((a, ar))
    return out


def read_field(path: Path, field: str) -> str:
    """[FIELD] value 형식에서 값 추출."""
    m = re.search(rf"^\[{re.escape(field)}\]\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else ""


# 종결 상태(아카이브·유저 회신 대상). 진행 중·질문대기는 절대 포함하지 않음.
# ★2026-08-05: needs-info 를 종결에서 제외한다(왕복 프로토콜, och §11).
#   needs-info = 워커가 오케에게 물음 → 아카이브 금지(답을 받아 재개해야 함).
TERMINAL_STATUSES = frozenset({"done", "error", "blocked", "failed"})
# 질문대기 상태(오케 개입 필요, 회신·아카이브 대상 아님). 왕복 프로토콜의 대기 지점.
NEEDS_INFO_STATUSES = frozenset({"needs-info", "waiting-answer"})
# 진행 중 동의어 → 정규형
_IN_PROGRESS_ALIASES = frozenset({
    "in-progress",
    "in_progress",
    "inprogress",
    "progress",
    "working",
    "running",
})


def normalize_status(raw: str) -> str:
    """ar_ [STATUS] 값을 소문자·구분자 정규화.

    - in_progress / IN-PROGRESS / inprogress → in-progress
    - 그 외는 strip+lower (하이픈/언더스코어 혼용 허용 위해 _ 를 - 로 통일하되
      needs-info 등은 유지)
    """
    s = (raw or "").strip().lower().replace("_", "-")
    # needs-info 가 needs-info 로 유지됨; in-progress 도 동일
    if s in _IN_PROGRESS_ALIASES or s.replace("-", "") in {a.replace("-", "").replace("_", "") for a in _IN_PROGRESS_ALIASES}:
        return "in-progress"
    return s or "unknown"


def read_response_status(ar_path: Path) -> str:
    return normalize_status(read_field(ar_path, "STATUS"))


def is_terminal_status(status: str) -> bool:
    return normalize_status(status) in TERMINAL_STATUSES


def is_in_progress_status(status: str) -> bool:
    return normalize_status(status) == "in-progress"


def is_needs_info_status(status: str) -> bool:
    """워커→오케 질문대기(needs-info / waiting-answer). 아카이브·회신 대상 아님.

    och §11 왕복 프로토콜의 '멈춤' 지점 — 오케가 [ANSWER] 를 a_ 에 append 하고
    워커를 재개시켜야 다음으로 넘어간다.
    """
    return normalize_status(status) in NEEDS_INFO_STATUSES


# ---------- 워커→오케 질문 왕복 (och §11) ----------

def read_question(ar_path: Path) -> str:
    """ar_ 의 워커 질문 추출: [QUESTION] 필드 우선, 없으면 '## 질문' 섹션.

    오케(세션)가 이 질문을 검토해 스스로 답하거나 유저에게 정제해 되묻는다.
    """
    q = read_field(ar_path, "QUESTION")
    if q:
        return q
    text = ar_path.read_text(encoding="utf-8")
    m = re.search(r"##\s*질문\s*\n(.+?)(?:\n##\s|\Z)", text, re.S)
    return (m.group(1).strip() if m else "").strip()


def has_pending_answer(a_path: Path) -> bool:
    """a_ 에 오케 답변([ANSWER]/'## 오케 답변')이 이미 append 됐는지.

    워커 재개 판정용 — 답이 붙었으면 워커가 이어서 처리해야 한다.
    """
    text = a_path.read_text(encoding="utf-8")
    return bool(re.search(r"^\[ANSWER\]\s*\S", text, re.M)) or bool(
        re.search(r"##\s*오케\s*답변", text)
    )


def append_answer(a_path: Path, answer: str, source: str = "오케") -> None:
    """오케(또는 유저) 답변을 a_ 지시서 끝에 append → 워커 재개 발판.

    - 워커가 needs-info 로 멈춘 뒤, 오케가 판단한 답(자답 또는 유저답 정제)을 여기 붙인다.
    - 붙인 뒤 짝 ar_ 를 지워 미처리로 되돌리면(재spawn) 워커가 답을 읽고 이어서 처리한다.
    """
    body = a_path.read_text(encoding="utf-8").rstrip()
    block = (
        f"\n\n[ANSWER] {source}\n"
        "## 오케 답변 (needs-info 에 대한 회신 — 이걸 반영해 이어서 처리하라)\n"
        f"{answer.strip()}\n"
    )
    a_path.write_text(body + block, encoding="utf-8")


def read_answer(a_path: Path) -> str:
    """a_ 에 append 된 오케 답변('## 오케 답변' 섹션 본문)을 읽는다.

    append_answer 의 짝. 워커가 재개될 때 [ANSWER] 본문을 코드로 꺼내 쓸 때 사용.
    (프롬프트는 지시서를 직접 읽게 안내하므로 필수는 아니나, 헬퍼 대칭·테스트용으로 제공.)
    """
    if not a_path.exists():
        return ""
    text = a_path.read_text(encoding="utf-8")
    m = re.search(r"##\s*오케\s*답변[^\n]*\n(.+)\Z", text, re.S)
    return (m.group(1).strip() if m else "").strip()


def summarize_response(ar_path: Path) -> str:
    """ar_*.txt 의 '## 결과' 섹션만 뽑아 회신용으로."""
    text = ar_path.read_text(encoding="utf-8")
    m = re.search(r"##\s*결과\s*\n(.+?)(?:\n##\s|\Z)", text, re.S)
    return (m.group(1).strip() if m else text.strip())[:1500]


def archive(*paths: Path) -> None:
    for p in paths:
        if p.exists():
            p.rename(DONE_DIR / p.name)
