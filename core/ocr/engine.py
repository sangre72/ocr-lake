"""Tesseract 기반 OCR 엔진.

입력 이미지 바이트 → 텍스트 추출. AI 구조화 파싱은 telegram_bot.ocr.structurer 에서 별도 처리.
"""

import io
import logging

import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

# 허용 이미지 포맷(허용목록) — 이 외 포맷은 거부
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF"}


class UnsupportedImageError(ValueError):
    """지원하지 않는 이미지 포맷"""


def extract_text(image_bytes: bytes, lang: str = "kor+eng") -> str:
    """이미지 바이트에서 텍스트를 추출한다.

    Args:
        image_bytes: 이미지 원본 바이트
        lang: tesseract 언어 코드(예: "kor+eng")

    Returns:
        추출된 텍스트(공백뿐이면 빈 문자열)

    Raises:
        UnsupportedImageError: 이미지가 아니거나 허용되지 않은 포맷인 경우
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()
        # verify() 이후 재오픈 필요(verify는 스트림을 소모)
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:
        raise UnsupportedImageError("이미지 파일을 열 수 없습니다.") from exc

    if image.format not in ALLOWED_FORMATS:
        raise UnsupportedImageError(f"지원하지 않는 이미지 포맷입니다: {image.format}")

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    text = pytesseract.image_to_string(image, lang=lang)
    return text.strip()
