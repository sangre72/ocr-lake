import os

from core.storage.db import (
    get_record,
    init_db,
    list_records,
    record_to_dict,
    save_record,
    update_structured_json,
)

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

    현재는 SqliteProvider 하나뿐. 향후 PostgreSQL/Elasticsearch/벡터DB 등을 추가할 때
    core/storage/base.py 의 StorageProvider Protocol 을 구현하고 여기 분기만 추가하면 된다.
    """
    provider = os.environ.get("STORAGE_PROVIDER", "sqlite").strip().lower()
    if provider == "sqlite":
        from core.storage.sqlite_provider import SqliteProvider

        return SqliteProvider()
    raise ValueError(f"지원하지 않는 STORAGE_PROVIDER: {provider!r} (현재 sqlite만 구현됨)")
