"""오피스 문서(PPTX·HWP) 관련 텔레그램 메시지 핸들러 (pdf_video_handlers.py 와 동일 패턴)"""

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from telegram_bot.config import load_config
from telegram_bot.handlers.common import is_allowed, save_record_safely
from core.hwp.engine import UnsupportedHwpError, process_hwp
from core.pptx.engine import UnsupportedPptxError, process_pptx

logger = logging.getLogger(__name__)

_PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def _is_pptx_document(document) -> bool:
    mime = (document.mime_type or "").lower()
    name = (document.file_name or "").lower()
    return mime == _PPTX_MIME or name.endswith(".pptx")


async def handle_pptx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    if not is_allowed(update, config.allowed_chat_ids):
        await update.message.reply_text("이 봇을 사용할 권한이 없습니다.")
        return

    message = update.message
    document = message.document
    if not document or not _is_pptx_document(document):
        return

    file_size = getattr(document, "file_size", None) or 0
    max_bytes = config.max_image_size_mb * 1024 * 1024
    if file_size and file_size > max_bytes:
        await message.reply_text(f"파일이 너무 큽니다(최대 {config.max_image_size_mb}MB).")
        return

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

    telegram_file = await document.get_file()
    pptx_bytes = bytes(await telegram_file.download_as_bytearray())

    try:
        result = await process_pptx(pptx_bytes, lang=config.ocr_lang)
    except UnsupportedPptxError as exc:
        await message.reply_text(f"PPTX를 처리할 수 없습니다: {exc}")
        return
    except Exception:
        logger.exception("PPTX 처리 중 오류")
        await message.reply_text("PPTX 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return

    save_record_safely(
        route="pptx_slides",
        chat_id=message.chat_id,
        extracted_text=result.combined_text,
        description=f"{result.slide_count}슬라이드",
    )

    if not result.combined_text.strip():
        await message.reply_text(f"PPTX({result.slide_count}슬라이드)에서 텍스트를 찾지 못했습니다.")
        return

    context.user_data["last_ocr_text"] = result.combined_text
    reply = (
        result.combined_text
        if len(result.combined_text) <= 3500
        else result.combined_text[:3500] + "\n…(이하 생략)"
    )
    await message.reply_text(f"[PPTX 인식 — {result.slide_count}슬라이드]\n추출된 텍스트:\n\n{reply}")


def _is_hwp_document(document) -> bool:
    name = (document.file_name or "").lower()
    mime = (document.mime_type or "").lower()
    return name.endswith(".hwp") or mime in (
        "application/x-hwp",
        "application/haansofthwp",
        "application/vnd.hancom.hwp",
    )


async def handle_hwp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    if not is_allowed(update, config.allowed_chat_ids):
        await update.message.reply_text("이 봇을 사용할 권한이 없습니다.")
        return

    message = update.message
    document = message.document
    if not document or not _is_hwp_document(document):
        return

    file_size = getattr(document, "file_size", None) or 0
    max_bytes = config.max_image_size_mb * 1024 * 1024
    if file_size and file_size > max_bytes:
        await message.reply_text(f"파일이 너무 큽니다(최대 {config.max_image_size_mb}MB).")
        return

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

    telegram_file = await document.get_file()
    hwp_bytes = bytes(await telegram_file.download_as_bytearray())

    try:
        result = process_hwp(hwp_bytes)
    except UnsupportedHwpError as exc:
        await message.reply_text(f"HWP 파일을 처리할 수 없습니다: {exc}")
        return
    except Exception:
        logger.exception("HWP 처리 중 오류")
        await message.reply_text("HWP 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return

    save_record_safely(
        route="hwp_document",
        chat_id=message.chat_id,
        extracted_text=result.combined_text,
        description="HWP 문서 처리",
    )

    context.user_data["last_ocr_text"] = result.combined_text
    reply = (
        result.combined_text
        if len(result.combined_text) <= 3500
        else result.combined_text[:3500] + "\n…(이하 생략)"
    )
    await message.reply_text(f"[HWP 인식]\n추출된 텍스트:\n\n{reply}")
