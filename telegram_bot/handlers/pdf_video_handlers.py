"""PDF·동영상 관련 텔레그램 메시지 핸들러 (ocr_handlers.py 와 별도 모듈 — code-structure.md §3-1)"""

import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from telegram_bot.config import load_config
from telegram_bot.handlers.common import is_allowed, save_record_safely
from core.pdf.engine import UnsupportedPdfError, process_pdf
from core.video.engine import UnsupportedVideoError, process_video

logger = logging.getLogger(__name__)


def _is_pdf_document(document) -> bool:
    mime = (document.mime_type or "").lower()
    return mime == "application/pdf"


async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    if not is_allowed(update, config.allowed_chat_ids):
        await update.message.reply_text("이 봇을 사용할 권한이 없습니다.")
        return

    message = update.message
    document = message.document
    if not document or not _is_pdf_document(document):
        return

    file_size = getattr(document, "file_size", None) or 0
    max_bytes = config.max_image_size_mb * 1024 * 1024
    if file_size and file_size > max_bytes:
        await message.reply_text(f"파일이 너무 큽니다(최대 {config.max_image_size_mb}MB).")
        return

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

    telegram_file = await document.get_file()
    pdf_bytes = bytes(await telegram_file.download_as_bytearray())

    try:
        result = await process_pdf(pdf_bytes, lang=config.ocr_lang)
    except UnsupportedPdfError as exc:
        await message.reply_text(f"PDF를 처리할 수 없습니다: {exc}")
        return
    except Exception:
        logger.exception("PDF 처리 중 오류")
        await message.reply_text("PDF 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return

    save_record_safely(
        route="pdf_document",
        chat_id=message.chat_id,
        extracted_text=result.combined_text,
        description=f"{result.page_count}페이지",
    )

    if not result.combined_text.strip():
        await message.reply_text(f"PDF({result.page_count}페이지)에서 텍스트를 찾지 못했습니다.")
        return

    context.user_data["last_ocr_text"] = result.combined_text
    reply = (
        result.combined_text
        if len(result.combined_text) <= 3500
        else result.combined_text[:3500] + "\n…(이하 생략)"
    )
    await message.reply_text(f"[PDF 인식 — {result.page_count}페이지]\n추출된 텍스트:\n\n{reply}")


def _is_video(message) -> bool:
    if message.video is not None:
        return True
    document = message.document
    if document and (document.mime_type or "").lower().startswith("video/"):
        return True
    return False


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    if not is_allowed(update, config.allowed_chat_ids):
        await update.message.reply_text("이 봇을 사용할 권한이 없습니다.")
        return

    message = update.message
    if not _is_video(message):
        return

    file_obj = message.video or message.document
    file_size = getattr(file_obj, "file_size", None) or 0
    max_bytes = config.max_image_size_mb * 1024 * 1024 * 5  # 동영상은 이미지보다 큰 편이라 5배 여유
    if file_size and file_size > max_bytes:
        await message.reply_text(f"동영상이 너무 큽니다(최대 {config.max_image_size_mb * 5}MB).")
        return

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.TYPING)

    telegram_file = await file_obj.get_file()
    video_bytes = bytes(await telegram_file.download_as_bytearray())

    try:
        result = await process_video(video_bytes, lang=config.ocr_lang)
    except UnsupportedVideoError as exc:
        await message.reply_text(f"동영상을 처리할 수 없습니다: {exc}")
        return
    except Exception:
        logger.exception("동영상 처리 중 오류")
        await message.reply_text("동영상 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
        return

    save_record_safely(
        route="video_frames",
        chat_id=message.chat_id,
        extracted_text=result.combined_text,
        description=f"{result.frame_count_sampled}프레임 샘플링, {len(result.document_frames)}건 텍스트 검출",
    )

    if not result.document_frames:
        await message.reply_text(
            f"동영상에서 텍스트를 찾지 못했습니다({result.frame_count_sampled}프레임 샘플링)."
        )
        return

    context.user_data["last_ocr_text"] = result.combined_text
    reply = (
        result.combined_text
        if len(result.combined_text) <= 3500
        else result.combined_text[:3500] + "\n…(이하 생략)"
    )
    await message.reply_text(
        f"[동영상 인식 — {len(result.document_frames)}개 프레임에서 텍스트 검출]\n\n{reply}"
    )
