"""OCR 관련 텔레그램 명령·메시지 핸들러"""

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from telegram_bot.config import load_config
from telegram_bot.ocr.engine import UnsupportedImageError
from telegram_bot.ocr.structurer import StructurerNotConfiguredError, structure_text
from telegram_bot.pipeline import process_image
from telegram_bot.storage import save_record

logger = logging.getLogger(__name__)


def _is_allowed(update: Update, allowed_chat_ids: list[int]) -> bool:
    if not allowed_chat_ids:
        return True
    chat_id = update.effective_chat.id if update.effective_chat else None
    return chat_id in allowed_chat_ids


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "OCR Lake 봇입니다.\n"
        "이미지를 보내주시면 텍스트를 추출해 드립니다.\n"
        "/structure 명령으로 마지막 추출 결과를 구조화(영수증·명함 등)할 수 있습니다."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    if not _is_allowed(update, config.allowed_chat_ids):
        await update.message.reply_text("이 봇을 사용할 권한이 없습니다.")
        return

    message = update.message
    if not message.photo and not (message.document and _is_image_document(message.document)):
        return

    file_obj = message.photo[-1] if message.photo else message.document
    file_size = getattr(file_obj, "file_size", None) or 0
    max_bytes = config.max_image_size_mb * 1024 * 1024
    if file_size and file_size > max_bytes:
        await message.reply_text(
            f"이미지가 너무 큽니다(최대 {config.max_image_size_mb}MB)."
        )
        return

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

    telegram_file = await file_obj.get_file()
    image_bytes = bytes(await telegram_file.download_as_bytearray())

    try:
        result = await process_image(image_bytes, lang=config.ocr_lang)
    except UnsupportedImageError as exc:
        await message.reply_text(f"이미지를 처리할 수 없습니다: {exc}")
        return
    except Exception:
        logger.exception("이미지 처리 중 오류")
        await message.reply_text("이미지 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return

    _save_record_safely(
        route=result.route,
        chat_id=message.chat_id,
        extracted_text=result.text,
        description=result.description,
    )

    if result.route in ("photo", "ambiguous_photo"):
        note = result.note or "이미지 설명 기능은 아직 미구현입니다."
        await message.reply_text(f"[사진으로 인식 — 설명 기능은 준비 중]\n{note}")
        return

    text = result.text
    if not text:
        await message.reply_text("이미지에서 텍스트를 찾지 못했습니다.")
        return

    context.user_data["last_ocr_text"] = text
    label = "[문서로 인식]" if result.route == "document" else "[문서로 판단(애매) — OCR 결과]"
    reply = text if len(text) <= 3500 else text[:3500] + "\n…(이하 생략)"
    await message.reply_text(f"{label}\n추출된 텍스트:\n\n{reply}")


def _save_record_safely(
    *, route: str, chat_id: int, extracted_text: str | None, description: str | None
) -> None:
    """이력 저장 실패가 텔레그램 응답 흐름을 막지 않도록 격리."""
    try:
        save_record(
            source="telegram",
            route=route,
            extracted_text=extracted_text,
            description=description,
            chat_id=chat_id,
        )
    except Exception:
        logger.exception("OCR 이력 저장 실패(텔레그램 응답에는 영향 없음)")


def _is_image_document(document) -> bool:
    mime = (document.mime_type or "").lower()
    return mime.startswith("image/")


async def structure(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    if not _is_allowed(update, config.allowed_chat_ids):
        await update.message.reply_text("이 봇을 사용할 권한이 없습니다.")
        return

    raw_text = context.user_data.get("last_ocr_text")
    if not raw_text:
        await update.message.reply_text("먼저 이미지를 보내 텍스트를 추출해주세요.")
        return

    try:
        result = await structure_text(raw_text)
    except StructurerNotConfiguredError as exc:
        await update.message.reply_text(str(exc))
        return
    except Exception:
        logger.exception("구조화 처리 중 오류")
        await update.message.reply_text("구조화 처리 중 오류가 발생했습니다.")
        return

    await update.message.reply_text(f"구조화 결과:\n{result}")
