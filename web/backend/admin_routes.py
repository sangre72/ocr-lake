"""작업 큐 현황판(관리자 전용) API.

design-guideline.md §7: system-internal 정보(poller status·queue count 등)는 일반 화면에 노출하지
않는다 — 이 라우터는 web/backend/routes.py(일반 API)와 분리된 별도 prefix(/api/admin)로 둔다.
`ADMIN_DASHBOARD_ENABLED` 환경변수로 기본 비활성화(이 프로젝트에 인증 시스템이 아직 없어, 최소한
명시적으로 켜지 않으면 응답하지 않는 방식으로 노출 범위를 좁힌다).

데이터 소스: telegram_bot/orchestrator/protocol_store.py 의 기존 함수 재사용(재발명 금지).
"""

import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from telegram_bot.orchestrator import protocol_store as ps

admin_router = APIRouter(prefix="/api/admin")
router = admin_router  # 하위 호환 별칭

# 최근 목록 표시 상한(과도한 응답 방지)
_RECENT_LIMIT = 30
# protocol_store.py 기준 repo 루트(telegram_bot/orchestrator/protocol_store.py 의 parents[2])
_REPO_ROOT = Path(ps.__file__).resolve().parents[2]
_A_SEQ_RE = re.compile(r"^a_([A-Za-z0-9]+)_")


def _admin_enabled() -> bool:
    return os.environ.get("ADMIN_DASHBOARD_ENABLED", "").strip().lower() in ("1", "true", "on")


def _require_admin_enabled() -> None:
    if not _admin_enabled():
        raise HTTPException(
            status_code=404,
            detail="관리자 대시보드가 비활성화되어 있습니다(ADMIN_DASHBOARD_ENABLED 환경변수 확인).",
        )


def _entry(
    path: Path,
    status: str | None = None,
    assigned: bool | None = None,
    worker: str | None = None,
) -> dict:
    return {
        "seq": path.stem,
        "title": ps.read_field(path, "TITLE") or path.stem,
        "path": str(path.relative_to(_REPO_ROOT)),
        "status": status,
        "assigned": assigned,
        "worker": worker,
    }


@admin_router.get("/jobs")
def get_job_queue_status() -> dict:
    """protocol/{u,a,done} 큐 파일을 읽어 대기·진행중·완료·에러 현황을 반환한다."""
    _require_admin_enabled()

    pending_u = sorted(ps.U_DIR.glob("u_*.txt"))
    a_files = sorted(ps.A_DIR.glob("a_*.txt"))

    pending_a: list[dict] = []
    in_progress: list[dict] = []
    error_recent: list[dict] = []

    for a_path in a_files:
        m = _A_SEQ_RE.match(a_path.name)
        seq = m.group(1) if m else a_path.stem
        ar_candidates = list(ps.A_DIR.glob(f"ar_{seq}_*.txt")) if m else []

        if not ar_candidates:
            pending_a.append(_entry(a_path, status="pending", assigned=False))
            continue

        ar_path = ar_candidates[0]
        status = ps.read_response_status(ar_path)
        worker = ps.read_field(ar_path, "WORKER") or None
        if ps.is_in_progress_status(status):
            in_progress.append(_entry(a_path, status=status, assigned=True, worker=worker))
        elif status == "error" or status == "failed":
            error_recent.append(_entry(ar_path, status=status, assigned=True, worker=worker))

    done_files = sorted(
        ps.DONE_DIR.glob("ar_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True
    )[:_RECENT_LIMIT]
    done_recent = [
        _entry(
            p,
            status=ps.read_response_status(p),
            assigned=True,
            worker=ps.read_field(p, "WORKER") or None,
        )
        for p in done_files
    ]

    return {
        "pendingU": [_entry(p, status="unprocessed") for p in pending_u],
        "pendingA": pending_a,
        "inProgress": in_progress,
        "doneRecent": done_recent,
        "errorRecent": error_recent,
    }
