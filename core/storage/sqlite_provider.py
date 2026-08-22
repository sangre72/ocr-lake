"""SqliteProvider — core/storage/db.py 의 함수형 API를 StorageProvider 인터페이스로 감싼 어댑터.

behavior-preserving: db.py 의 실제 로직은 그대로 두고 얇게 위임만 한다(회귀 방지, 재발명 금지).
"""

from typing import Optional

from core.storage import db
from core.storage.db import OcrRecord, Route, Source


class SqliteProvider:
    def init(self) -> None:
        db.init_db()

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
    ) -> int:
        return db.save_record(
            source=source,
            route=route,
            image_path=image_path,
            extracted_text=extracted_text,
            description=description,
            structured_json=structured_json,
            chat_id=chat_id,
        )

    def update_structured_json(self, record_id: int, structured_json: dict) -> None:
        db.update_structured_json(record_id, structured_json)

    def list_records(self, page: int = 1, size: int = 20) -> tuple[list[OcrRecord], int]:
        return db.list_records(page=page, size=size)

    def get_record(self, record_id: int) -> Optional[OcrRecord]:
        return db.get_record(record_id)
