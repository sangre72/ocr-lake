"""이미지 처리 분기 파이프라인.

classify_image 결과에 따라 OCR(document) / 이미지 설명(photo) / OCR 우선 시도 후 폴백(ambiguous) 로
분기한다. handlers 는 이 모듈의 process_image() 만 호출하면 된다.
"""

import logging
import os
from dataclasses import dataclass
from typing import Literal

from core.classify.engine import classify_image_with_confidence
from core.ocr.engine import extract_text
from core.vision.describer import DescriberNotConfiguredError, image_describe

logger = logging.getLogger(__name__)

# ambiguous 분기에서 OCR 결과를 "텍스트 있음"으로 볼 최소 글자 수
AMBIGUOUS_OCR_MIN_CHARS = 10

# 클라우드 OCR provider 폴백(§14-4) — GOOGLE_CLOUD_VISION_API_KEY 등 자격증명이 .env 에 있을 때만
# 시도한다. 자격증명이 없으면 기존 Tesseract 결과 그대로 유지(회귀 없음).
_CLOUD_PROVIDER_ENV_CHECKS = {
    "google": "GOOGLE_CLOUD_VISION_API_KEY",
    # aws/azure/naver 는 인터페이스만 준비된 상태(a_21) — 자격증명 확보 시 여기 추가
}


def _get_configured_cloud_provider():
    """환경변수에 자격증명이 설정된 클라우드 provider 가 있으면 인스턴스를 반환, 없으면 None."""
    if os.environ.get(_CLOUD_PROVIDER_ENV_CHECKS["google"], "").strip():
        from core.ocr.providers.google_provider import GoogleVisionProvider

        return GoogleVisionProvider()
    return None

Route = Literal["document", "photo", "ambiguous_ocr", "ambiguous_photo"]


@dataclass
class PipelineResult:
    route: Route
    text: str | None = None
    description: str | None = None
    note: str | None = None
    confidence: float | None = None


async def process_image(image_bytes: bytes, lang: str = "kor+eng") -> PipelineResult:
    """이미지를 분류 후 적절한 경로(OCR/이미지설명)로 처리한다.

    Args:
        image_bytes: 이미지 원본 바이트
        lang: tesseract 언어 코드

    Returns:
        PipelineResult: 어떤 경로로 처리됐는지와 결과(text 또는 description), classify 단계의
        평균 confidence(§14-7 1단계 — ocr_records.original_confidence 저장용)

    Raises:
        UnsupportedImageError: classify_image/extract_text 에서 이미지 처리 불가 시 전파
    """
    kind, confidence = classify_image_with_confidence(image_bytes, lang=lang)
    logger.debug("process_image classify=%s confidence=%.1f", kind, confidence)

    if kind == "document":
        text = extract_text(image_bytes, lang=lang)
        return PipelineResult(route="document", text=text, confidence=confidence)

    if kind == "photo":
        result = await _describe_or_note(image_bytes, route="photo")
        result.confidence = confidence
        return result

    # ambiguous: OCR 먼저 시도, 텍스트가 임계값 미만이면 클라우드 provider 폴백 시도 후 photo 경로로 폴백
    text = extract_text(image_bytes, lang=lang)
    if len(text) >= AMBIGUOUS_OCR_MIN_CHARS:
        return PipelineResult(route="ambiguous_ocr", text=text, confidence=confidence)

    cloud_provider = _get_configured_cloud_provider()
    if cloud_provider is not None:
        try:
            cloud_result = cloud_provider.extract_text(image_bytes, lang=lang)
            if len(cloud_result.text) >= AMBIGUOUS_OCR_MIN_CHARS:
                logger.info("Tesseract 결과 부족 — 클라우드 provider 폴백으로 텍스트 확보")
                return PipelineResult(route="ambiguous_ocr", text=cloud_result.text, confidence=confidence)
        except Exception:
            logger.exception("클라우드 provider 폴백 실패 — 기존 photo 경로로 계속 진행")

    result = await _describe_or_note(image_bytes, route="ambiguous_photo")
    result.confidence = confidence
    return result


async def _describe_or_note(image_bytes: bytes, route: Route) -> PipelineResult:
    try:
        description = await image_describe(image_bytes)
        return PipelineResult(route=route, description=description)
    except DescriberNotConfiguredError as exc:
        return PipelineResult(route=route, note=str(exc))
