"""OCR/PDF/동영상 핸들러 공용 헬퍼(권한 검사·이력 저장)"""

import logging

from telegram import Update

from core.storage import save_record

logger = logging.getLogger(__name__)


def is_allowed(update: Update, allowed_chat_ids: list[int]) -> bool:
    if not allowed_chat_ids:
        return True
    chat_id = update.effective_chat.id if update.effective_chat else None
    return chat_id in allowed_chat_ids


def save_record_safely(
    *,
    route: str,
    chat_id: int,
    extracted_text: str | None,
    description: str | None,
    structured_json: dict | None = None,
) -> None:
    """이력 저장 실패가 텔레그램 응답 흐름을 막지 않도록 격리."""
    try:
        save_record(
            source="telegram",
            route=route,
            extracted_text=extracted_text,
            description=description,
            structured_json=structured_json,
            chat_id=chat_id,
        )
    except Exception:
        logger.exception("OCR 이력 저장 실패(텔레그램 응답에는 영향 없음)")
