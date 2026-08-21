"""OCR Lake FastAPI 앱 엔트리포인트.

실행: python3 -m uvicorn web.backend.main:app --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.storage import init_db
from web.backend.routes import router

app = FastAPI(title="OCR Lake API")

# 로컬 개발 origin만 허용(security-guideline.md — CORS 제한).
# 기본 포트(3000)가 다른 로컬 프로세스에 점유된 경우를 대비해 Next.js dev 서버의 자동 대체
# 포트(3001)도 개발 환경에 한해 허용한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
