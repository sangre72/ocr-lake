"""OCR 처리 이력 영속화 — SQLite(표준 라이브러리 sqlite3, 별도 서버 불요).

DB 컬럼은 스네이크케이스(SQLite 관례), API 응답/프론트 필드는 camelCase 로 변환해 내보낸다
(naming-standard.md: 물리명↔JS var 매핑은 record_to_dict() 가 담당).
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal, Optional

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ocr_lake.db"

Source = Literal["telegram", "web"]
Route = Literal[
    "document", "photo", "ambiguous_ocr", "ambiguous_photo",
    "pdf_document", "video_frames",
]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ocr_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    source TEXT NOT NULL CHECK (source IN ('telegram', 'web')),
    image_path TEXT,
    route TEXT NOT NULL CHECK (route IN (
        'document', 'photo', 'ambiguous_ocr', 'ambiguous_photo',
        'pdf_document', 'video_frames'
    )),
    extracted_text TEXT,
    description TEXT,
    structured_json TEXT,
    chat_id INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ocr_records_created_at ON ocr_records(created_at DESC);
"""


@dataclass
class OcrRecord:
    id: int
    created_at: str
    source: Source
    image_path: Optional[str]
    route: Route
    extracted_text: Optional[str]
    description: Optional[str]
    structured_json: Optional[dict]
    chat_id: Optional[int]


def init_db() -> None:
    """DB 파일·테이블이 없으면 생성한다. 앱 시작 시 1회 호출."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_record(
    *,
    source: Source,
    route: Route,
    image_path: Optional[str] = None,
    extracted_text: Optional[str] = None,
    description: Optional[str] = None,
    structured_json: Optional[dict] = None,
    chat_id: Optional[int] = None,
) -> int:
    """처리 결과 1건을 저장하고 새 레코드 id 를 반환한다."""
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO ocr_records
                (source, image_path, route, extracted_text, description, structured_json, chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source,
                image_path,
                route,
                extracted_text,
                description,
                json.dumps(structured_json, ensure_ascii=False) if structured_json else None,
                chat_id,
            ),
        )
        return cur.lastrowid


def update_structured_json(record_id: int, structured_json: dict) -> None:
    """기존 레코드의 structured_json 컬럼을 갱신한다(온디맨드 AI 구조화 결과 저장)."""
    with _connect() as conn:
        conn.execute(
            "UPDATE ocr_records SET structured_json = ? WHERE id = ?",
            (json.dumps(structured_json, ensure_ascii=False), record_id),
        )


def _row_to_record(row: sqlite3.Row) -> OcrRecord:
    structured = json.loads(row["structured_json"]) if row["structured_json"] else None
    return OcrRecord(
        id=row["id"],
        created_at=row["created_at"],
        source=row["source"],
        image_path=row["image_path"],
        route=row["route"],
        extracted_text=row["extracted_text"],
        description=row["description"],
        structured_json=structured,
        chat_id=row["chat_id"],
    )


def list_records(page: int = 1, size: int = 20) -> tuple[list[OcrRecord], int]:
    """(레코드 목록, 전체 건수) 를 최신순으로 반환한다."""
    page = max(page, 1)
    size = min(max(size, 1), 100)
    offset = (page - 1) * size
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM ocr_records").fetchone()["c"]
        rows = conn.execute(
            "SELECT * FROM ocr_records ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (size, offset),
        ).fetchall()
    return [_row_to_record(r) for r in rows], total


def get_record(record_id: int) -> Optional[OcrRecord]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM ocr_records WHERE id = ?", (record_id,)
        ).fetchone()
    return _row_to_record(row) if row else None


def record_to_dict(record: OcrRecord) -> dict:
    """DB 스네이크케이스 → API/프론트 camelCase 변환(naming-standard.md)."""
    return {
        "id": record.id,
        "createdAt": record.created_at,
        "source": record.source,
        "imagePath": record.image_path,
        "route": record.route,
        "extractedText": record.extracted_text,
        "description": record.description,
        "structuredJson": record.structured_json,
        "chatId": record.chat_id,
    }
