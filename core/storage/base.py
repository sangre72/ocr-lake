"""저장소 Provider 추상 인터페이스.

향후 다른 저장소(PostgreSQL 등 RDB, Elasticsearch, 벡터DB 등)를 추가할 때 이 Protocol만
구현하면 core/storage/__init__.py 의 팩토리가 골라 쓸 수 있다. 지금은 SqliteProvider 하나뿐.
"""

from typing import Optional, Protocol

from core.storage.db import OcrRecord, Route, Source


class StorageProvider(Protocol):
    def init(self) -> None:
        """저장소 초기화(테이블/인덱스 생성 등). 앱 시작 시 1회 호출."""
        ...

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
        ...

    def update_structured_json(self, record_id: int, structured_json: dict) -> None:
        ...

    def list_records(self, page: int = 1, size: int = 20) -> tuple[list[OcrRecord], int]:
        ...

    def get_record(self, record_id: int) -> Optional[OcrRecord]:
        ...
