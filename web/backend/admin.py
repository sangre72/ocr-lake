"""관리자 전용 작업 큐 현황 집계.

design-guideline.md §7: system-internal 정보(작업 큐·워커 배정 등)는 일반 화면에 노출 금지.
이 모듈은 /api/admin/* 경로에서만 사용하며, 일반 API(routes.py)와 분리한다.

데이터 소스: telegram_bot/orchestrator/protocol_store.py 의 기존 함수 재사용(재발명 금지).
"""

from __future__ import annotations

from telegram_bot.orchestrator import protocol_store as ps


def _entry(path, extra: dict | None = None) -> dict:
    title = ps.read_field(path, "TITLE") or ps.read_field(path, "USERNAME") or path.stem
    entry = {
        "seq": path.stem,
        "title": title,
        "path": ps.rel_from_repo(path),
    }
    if extra:
        entry.update(extra)
    return entry


def collect_job_queue_status() -> dict:
    """protocol/u, protocol/a(+ar), protocol/done 을 읽어 상태별로 집계한다."""
    pending_u = [_entry(p) for p in sorted(ps.U_DIR.glob("u_*.txt"))]

    pending_a: list[dict] = []
    in_progress: list[dict] = []
    done_recent: list[dict] = []
    error_recent: list[dict] = []

    for a_path in sorted(ps.A_DIR.glob("a_*.txt")):
        m_seq = ps.read_field(a_path, "PARENT")
        ar_path = ps.A_DIR / a_path.name.replace("a_", "ar_", 1)
        if not ar_path.exists():
            pending_a.append(_entry(a_path, {"assigned": False}))
            continue
        status = ps.read_response_status(ar_path)
        if ps.is_in_progress_status(status) or ps.is_needs_info_status(status):
            in_progress.append(_entry(a_path, {"status": status}))
        elif status in ("error", "failed", "blocked"):
            error_recent.append(_entry(a_path, {"status": status}))
        elif ps.is_terminal_status(status):
            done_recent.append(_entry(a_path, {"status": status}))

    for a_path in sorted(ps.DONE_DIR.glob("a_*.txt"), reverse=True)[:20]:
        ar_path = ps.DONE_DIR / a_path.name.replace("a_", "ar_", 1)
        status = ps.read_response_status(ar_path) if ar_path.exists() else "done"
        entry = _entry(a_path, {"status": status})
        if status in ("error", "failed", "blocked"):
            error_recent.append(entry)
        else:
            done_recent.append(entry)

    return {
        "pendingU": pending_u,
        "pendingA": pending_a,
        "inProgress": in_progress,
        "doneRecent": done_recent[:20],
        "errorRecent": error_recent[:20],
    }
