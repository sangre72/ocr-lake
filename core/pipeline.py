"""이미지 처리 분기 파이프라인.

classify_image 결과에 따라 OCR(document) / 이미지 설명(photo) / OCR 우선 시도 후 폴백(ambiguous) 로
분기한다. handlers 는 이 모듈의 process_image() 만 호출하면 된다.
"""

import logging
from dataclasses import dataclass
from typing import Literal

from core.classify.engine import classify_image
from core.ocr.engine import extract_text
from core.vision.describer import DescriberNotConfiguredError, image_describe

logger = logging.getLogger(__name__)

# ambiguous 분기에서 OCR 결과를 "텍스트 있음"으로 볼 최소 글자 수
AMBIGUOUS_OCR_MIN_CHARS = 10

Route = Literal["document", "photo", "ambiguous_ocr", "ambiguous_photo"]


@dataclass
class PipelineResult:
    route: Route
    text: str | None = None
    description: str | None = None
    note: str | None = None


async def process_image(image_bytes: bytes, lang: str = "kor+eng") -> PipelineResult:
    """이미지를 분류 후 적절한 경로(OCR/이미지설명)로 처리한다.

    Args:
        image_bytes: 이미지 원본 바이트
        lang: tesseract 언어 코드

    Returns:
        PipelineResult: 어떤 경로로 처리됐는지와 결과(text 또는 description)

    Raises:
        UnsupportedImageError: classify_image/extract_text 에서 이미지 처리 불가 시 전파
    """
    kind = classify_image(image_bytes, lang=lang)
    logger.debug("process_image classify=%s", kind)

    if kind == "document":
        text = extract_text(image_bytes, lang=lang)
        return PipelineResult(route="document", text=text)

    if kind == "photo":
        return await _describe_or_note(image_bytes, route="photo")

    # ambiguous: OCR 먼저 시도, 텍스트가 임계값 미만이면 photo 경로로 폴백
    text = extract_text(image_bytes, lang=lang)
    if len(text) >= AMBIGUOUS_OCR_MIN_CHARS:
        return PipelineResult(route="ambiguous_ocr", text=text)

    return await _describe_or_note(image_bytes, route="ambiguous_photo")


async def _describe_or_note(image_bytes: bytes, route: Route) -> PipelineResult:
    try:
        description = await image_describe(image_bytes)
        return PipelineResult(route=route, description=description)
    except DescriberNotConfiguredError as exc:
        return PipelineResult(route=route, note=str(exc))
