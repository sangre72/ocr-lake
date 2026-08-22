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
    original_confidence: float | None = None,
) -> int | None:
    """이력 저장 실패가 텔레그램 응답 흐름을 막지 않도록 격리.

    Returns:
        저장된 record id. 저장 실패 시 None(§14-7 2단계 "수정하기" 버튼이 이 id로 레코드를 특정한다 —
        실패해도 None 반환만 할 뿐 텔레그램 응답 흐름 자체는 막지 않음).
    """
    try:
        return save_record(
            source="telegram",
            route=route,
            extracted_text=extracted_text,
            description=description,
            structured_json=structured_json,
            chat_id=chat_id,
            original_confidence=original_confidence,
        )
    except Exception:
        logger.exception("OCR 이력 저장 실패(텔레그램 응답에는 영향 없음)")
        return None
