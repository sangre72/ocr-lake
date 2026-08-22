"""이미지 유형 분류 게이트: 문서(텍스트 위주) vs 사진(사물·장비 등) 판별.

Tesseract image_to_data 의 단어별 confidence·인식 단어 수를 heuristic 판별 근거로 쓴다.
문서/영수증/명함처럼 텍스트가 조밀하고 신뢰도 높게 인식되면 "document",
텍스트가 거의 없거나 신뢰도가 낮으면 "photo", 그 경계는 "ambiguous"로 분류한다.
"""

import io
import logging
from typing import Literal

import pytesseract
from PIL import Image

from core.ocr.engine import ALLOWED_FORMATS, UnsupportedImageError

logger = logging.getLogger(__name__)

ImageKind = Literal["document", "photo", "ambiguous"]

# 판별 임계값 — 실측(스모크 테스트)으로 조정된 값.
# 신뢰도 있는 단어(conf >= 0 인 것 중 conf 값) 평균과 개수로 판별.
_MIN_WORDS_FOR_DOCUMENT = 5
_MIN_AVG_CONF_FOR_DOCUMENT = 60.0
_MAX_WORDS_FOR_PHOTO = 2
_MAX_AVG_CONF_FOR_PHOTO = 40.0


def _load_image(image_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify()
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:
        raise UnsupportedImageError("이미지 파일을 열 수 없습니다.") from exc
    if image.format not in ALLOWED_FORMATS:
        raise UnsupportedImageError(f"지원하지 않는 이미지 포맷입니다: {image.format}")
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    return image


def _text_signal(image: Image.Image, lang: str) -> tuple[int, float]:
    """(신뢰도 있는 단어 수, 평균 confidence)를 반환한다."""
    data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
    confs = []
    for text, conf in zip(data.get("text", []), data.get("conf", [])):
        if not text.strip():
            continue
        try:
            c = float(conf)
        except (TypeError, ValueError):
            continue
        if c < 0:
            continue
        confs.append(c)
    if not confs:
        return (0, 0.0)
    return (len(confs), sum(confs) / len(confs))


def classify_image(image_bytes: bytes, lang: str = "kor+eng") -> ImageKind:
    """이미지가 문서(document)인지 사진(photo)인지, 애매(ambiguous)한지 분류한다.

    Args:
        image_bytes: 이미지 원본 바이트
        lang: tesseract 언어 코드

    Returns:
        "document" | "photo" | "ambiguous"

    Raises:
        UnsupportedImageError: 이미지가 아니거나 허용되지 않은 포맷인 경우
    """
    kind, _ = classify_image_with_confidence(image_bytes, lang=lang)
    return kind


def classify_image_with_confidence(
    image_bytes: bytes, lang: str = "kor+eng"
) -> tuple[ImageKind, float]:
    """classify_image 와 동일 판정 로직이되, 평균 confidence 도 함께 반환한다.

    §14-7(OCR 오인식 대처) 1단계 — 지금까지 계산만 하고 버려지던 avg_conf 를
    ocr_records.original_confidence 로 저장하기 위해 신설(behavior-preserving, classify_image
    자체는 이 함수의 kind 만 취하도록 유지해 기존 호출부에 영향 없음).
    """
    image = _load_image(image_bytes)
    word_count, avg_conf = _text_signal(image, lang)

    if word_count >= _MIN_WORDS_FOR_DOCUMENT and avg_conf >= _MIN_AVG_CONF_FOR_DOCUMENT:
        return "document", avg_conf
    if word_count <= _MAX_WORDS_FOR_PHOTO and avg_conf <= _MAX_AVG_CONF_FOR_PHOTO:
        return "photo", avg_conf
    return "ambiguous", avg_conf
