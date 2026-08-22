"""OCR 관련 텔레그램 명령·메시지 핸들러"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from telegram_bot.config import load_config
from telegram_bot.handlers.common import is_allowed, save_record_safely
from core.ocr.engine import UnsupportedImageError
from core.ocr.structurer import StructurerNotConfiguredError, structure_text
from core.pipeline import process_image
from core.storage import update_corrected_text

logger = logging.getLogger(__name__)

# "수정하기" 콜백 데이터 프리픽스(record id 이어붙임) — §14-7 2단계
_CORRECT_CALLBACK_PREFIX = "ocr_correct:"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "OCR Lake 봇입니다.\n"
        "이미지를 보내주시면 텍스트를 추출해 드립니다.\n"
        "/structure 명령으로 마지막 추출 결과를 구조화(영수증·명함 등)할 수 있습니다."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    if not is_allowed(update, config.allowed_chat_ids):
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

    record_id = save_record_safely(
        route=result.route,
        chat_id=message.chat_id,
        extracted_text=result.text,
        description=result.description,
        original_confidence=result.confidence,
    )

    if result.route in ("photo", "ambiguous_photo"):
        if result.description:
            await message.reply_text(f"[사진으로 인식]\n{result.description}")
        else:
            note = result.note or "이미지 설명 기능을 사용할 수 없습니다."
            await message.reply_text(f"[사진으로 인식 — 설명 기능은 준비 중]\n{note}")
        return

    text = result.text
    if not text:
        await message.reply_text("이미지에서 텍스트를 찾지 못했습니다.")
        return

    context.user_data["last_ocr_text"] = text
    label = "[문서로 인식]" if result.route == "document" else "[문서로 판단(애매) — OCR 결과]"
    reply = text if len(text) <= 3500 else text[:3500] + "\n…(이하 생략)"

    reply_markup = None
    if record_id is not None:
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("✏️ 수정하기", callback_data=f"{_CORRECT_CALLBACK_PREFIX}{record_id}")]]
        )
    await message.reply_text(f"{label}\n추출된 텍스트:\n\n{reply}", reply_markup=reply_markup)


async def handle_correct_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """"수정하기" 인라인 버튼 클릭 — 다음 텍스트 메시지를 correctedText 로 받을 준비를 한다."""
    query = update.callback_query
    if query is None or not query.data or not query.data.startswith(_CORRECT_CALLBACK_PREFIX):
        return
    await query.answer()

    try:
        record_id = int(query.data[len(_CORRECT_CALLBACK_PREFIX):])
    except ValueError:
        return

    context.user_data["pending_correction_record_id"] = record_id
    if query.message:
        await query.message.reply_text(
            "수정할 텍스트를 이어서 보내주세요(원본 텍스트는 그대로 보존되고, 이 내용으로 교정본만 저장됩니다)."
        )


async def handle_correction_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """"수정하기" 버튼 이후 도착한 텍스트를 correctedText 로 저장한다.

    Returns:
        True 면 이 메시지를 교정 입력으로 소비했다는 뜻(호출부가 다른 핸들러로 넘기지 않게).
        False 면 대기 중인 교정 요청이 없어 아무 것도 하지 않았다는 뜻.
    """
    record_id = context.user_data.pop("pending_correction_record_id", None)
    if record_id is None:
        return False

    text = update.message.text if update.message else None
    if not text:
        return False

    try:
        update_corrected_text(record_id, text)
    except Exception:
        logger.exception("교정 텍스트 저장 실패")
        await update.message.reply_text("교정 텍스트 저장 중 오류가 발생했습니다.")
        return True

    await update.message.reply_text(f"✅ 수정 완료(레코드 #{record_id}). 원본은 그대로 보존됩니다.")
    return True


def _is_image_document(document) -> bool:
    mime = (document.mime_type or "").lower()
    return mime.startswith("image/")


async def structure(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    if not is_allowed(update, config.allowed_chat_ids):
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
