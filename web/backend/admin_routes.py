"""관리자 전용 라우트 — 작업 큐 현황(/api/admin/jobs).

design-guideline.md §7: system-internal 노출 금지 원칙에 따라 일반 라우터(routes.py)와 분리하고,
main.py 에서 ADMIN_DASHBOARD_ENABLED=1 일 때만 등록한다. 인증 시스템은 이 프로젝트에 아직 없어
완전한 인가까지는 이번 스코프가 아니다 — 경로 분리 + 명시적 활성화 스위치까지만 달성한다.
"""

from fastapi import APIRouter

from web.backend.admin import collect_job_queue_status

admin_router = APIRouter(prefix="/api/admin")


@admin_router.get("/jobs")
async def job_queue_status() -> dict:
    return collect_job_queue_status()
