"""PostgreSQL Storage Provider — core/storage/base.py 의 StorageProvider 인터페이스 구현.

SQLite provider(sqlite_provider.py)와 동일한 스키마(ocr_records)를 PostgreSQL DDL로 재현한다.
pgvector 확장을 활성화해 텍스트 임베딩 컬럼(embedding vector)을 준비해둔다 — 실제 임베딩 생성
모델 연동은 이번 스코프 밖(컬럼/스켈레톤만, docs/tech-spec.md 에 스코프 경계 명시).
"""

import json
import os
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from core.storage.db import OcrRecord, Route, Source

# pgvector 임베딩 차원(로컬 임베딩 모델 연동 시 실제 모델의 출력 차원에 맞춰 조정 필요 — 스켈레톤 값)
EMBEDDING_DIM = 768

_SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS ocr_records (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source TEXT NOT NULL CHECK (source IN ('telegram', 'web', 'discord', 'slack')),
    image_path TEXT,
    route TEXT NOT NULL CHECK (route IN (
        'document', 'photo', 'ambiguous_ocr', 'ambiguous_photo',
        'pdf_document', 'video_frames', 'pptx_slides', 'hwp_document', 'docx_document'
    )),
    extracted_text TEXT,
    description TEXT,
    structured_json JSONB,
    chat_id BIGINT,
    embedding vector({EMBEDDING_DIM}),
    corrected_text TEXT,
    is_corrected BOOLEAN NOT NULL DEFAULT false,
    corrected_at TIMESTAMPTZ,
    original_confidence REAL
);
CREATE INDEX IF NOT EXISTS idx_ocr_records_created_at ON ocr_records(created_at DESC);
ALTER TABLE ocr_records ADD COLUMN IF NOT EXISTS corrected_text TEXT;
ALTER TABLE ocr_records ADD COLUMN IF NOT EXISTS is_corrected BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE ocr_records ADD COLUMN IF NOT EXISTS corrected_at TIMESTAMPTZ;
ALTER TABLE ocr_records ADD COLUMN IF NOT EXISTS original_confidence REAL;
"""


def _get_dsn() -> str:
    """OCR_LAKE_DATABASE_URL(우선) 또는 POSTGRES_* 개별 변수로 연결 문자열을 구성한다.

    ★일반 DATABASE_URL 이 아닌 OCR_LAKE_DATABASE_URL 을 쓴다 — 이 레포의 .env.example 최상단에
    다른 프로젝트(skyrecruit)용 DATABASE_URL 이 이미 있어, 실수로 그 값을 재사용해 남의 DB에
    연결하는 사고를 막기 위함(이 프로젝트 전용 DB만 사용 원칙).
    """
    dsn = os.environ.get("OCR_LAKE_DATABASE_URL", "").strip()
    if dsn:
        return dsn

    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "")
    password = os.environ.get("POSTGRES_PASSWORD", "")
    dbname = os.environ.get("POSTGRES_DB", "ocr_lake")

    auth = f"{user}:{password}@" if user else ""
    return f"postgresql://{auth}{host}:{port}/{dbname}"


class PostgresProvider:
    def __init__(self, dsn: Optional[str] = None) -> None:
        self._dsn = dsn or _get_dsn()

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, row_factory=dict_row)

    def init(self) -> None:
        with self._connect() as conn:
            conn.execute(_SCHEMA)
            conn.commit()

    def save_record(
        self,
        *,
        source: Source,
        route: Route,
        image_path: Optional[str] = None,
        extracted_text: Optional[str] = None,
        description: Optional[str] = None,
        structured_json: Optional[dict] = None,
        chat_id: Optional[int] = None,
        original_confidence: Optional[float] = None,
    ) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO ocr_records
                    (source, image_path, route, extracted_text, description, structured_json, chat_id, original_confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    source,
                    image_path,
                    route,
                    extracted_text,
                    description,
                    json.dumps(structured_json, ensure_ascii=False) if structured_json else None,
                    chat_id,
                    original_confidence,
                ),
            ).fetchone()
            conn.commit()
            return row["id"]

    def update_structured_json(self, record_id: int, structured_json: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE ocr_records SET structured_json = %s WHERE id = %s",
                (json.dumps(structured_json, ensure_ascii=False), record_id),
            )
            conn.commit()

    def update_corrected_text(self, record_id: int, corrected_text: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE ocr_records
                SET corrected_text = %s, is_corrected = true, corrected_at = now()
                WHERE id = %s
                """,
                (corrected_text, record_id),
            )
            conn.commit()

    def list_records(self, page: int = 1, size: int = 20) -> tuple[list[OcrRecord], int]:
        page = max(page, 1)
        size = min(max(size, 1), 100)
        offset = (page - 1) * size
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM ocr_records").fetchone()["c"]
            rows = conn.execute(
                "SELECT * FROM ocr_records ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
                (size, offset),
            ).fetchall()
        return [_row_to_record(r) for r in rows], total

    def get_record(self, record_id: int) -> Optional[OcrRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM ocr_records WHERE id = %s", (record_id,)
            ).fetchone()
        return _row_to_record(row) if row else None


def _row_to_record(row: dict) -> OcrRecord:
    return OcrRecord(
        id=row["id"],
        created_at=str(row["created_at"]),
        source=row["source"],
        image_path=row["image_path"],
        route=row["route"],
        extracted_text=row["extracted_text"],
        description=row["description"],
        structured_json=row["structured_json"],
        chat_id=row["chat_id"],
        corrected_text=row.get("corrected_text"),
        is_corrected=bool(row.get("is_corrected")),
        corrected_at=str(row["corrected_at"]) if row.get("corrected_at") else None,
        original_confidence=row.get("original_confidence"),
    )
