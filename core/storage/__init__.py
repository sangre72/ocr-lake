"""전역 저장소 진입점.

★함수형 API(init_db/save_record/get_record/list_records/update_structured_json)는 get_storage_provider()
로 선택된 provider 에 위임한다 — web/backend·telegram_bot/handlers 등 호출부는 이 모듈만 import 하면
STORAGE_PROVIDER 환경변수에 따라 실제 저장소가 SQLite/PostgreSQL 등으로 자동 전환된다(코드 변경 불요).
"""

import os

from core.storage.db import record_to_dict

__all__ = [
    "init_db",
    "save_record",
    "list_records",
    "get_record",
    "record_to_dict",
    "update_structured_json",
    "get_storage_provider",
]


def get_storage_provider():
    """STORAGE_PROVIDER 환경변수로 저장소 provider 를 선택하는 팩토리(기본값 sqlite).

    현재는 SqliteProvider·PostgresProvider 두 개. 향후 Elasticsearch/Hadoop 등을 추가할 때
    core/storage/base.py 의 StorageProvider Protocol 을 구현하고 여기 분기만 추가하면 된다.
    """
    provider = os.environ.get("STORAGE_PROVIDER", "sqlite").strip().lower()
    if provider == "sqlite":
        from core.storage.sqlite_provider import SqliteProvider

        return SqliteProvider()
    if provider == "postgres":
        from core.storage.postgres_provider import PostgresProvider

        return PostgresProvider()
    raise ValueError(
        f"지원하지 않는 STORAGE_PROVIDER: {provider!r} (현재 sqlite, postgres 구현됨)"
    )


def init_db() -> None:
    get_storage_provider().init()


def save_record(**kwargs) -> int:
    return get_storage_provider().save_record(**kwargs)


def list_records(page: int = 1, size: int = 20):
    return get_storage_provider().list_records(page=page, size=size)


def get_record(record_id: int):
    return get_storage_provider().get_record(record_id)


def update_structured_json(record_id: int, structured_json: dict) -> None:
    get_storage_provider().update_structured_json(record_id, structured_json)
