"""Slack 파일 업로드 → core 파이프라인 라우팅 (discord_bot/handlers.py 와 동일 패턴 — 채널 대칭).

같은 입력(이미지/PDF/동영상/오피스문서)은 텔레그램·웹·Discord와 동일하게 core 의 같은 함수를 호출한다
(feature-consistency-guideline.md 채널 대칭 원칙).
"""

import logging

from core.docx.engine import process_docx
from core.hwp.engine import process_hwp
from core.pdf.engine import process_pdf
from core.pipeline import process_image
from core.pptx.engine import process_pptx
from core.storage import save_record
from core.video.engine import process_video

logger = logging.getLogger(__name__)

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif")
_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".avi")


def is_allowed(channel_id: str, allowed_channel_ids: list[str]) -> bool:
    if not allowed_channel_ids:
        return True
    return channel_id in allowed_channel_ids


def _save_record_safely(*, route: str, extracted_text, description) -> None:
    """이력 저장 실패가 Slack 응답 흐름을 막지 않도록 격리(telegram_bot 패턴과 동일)."""
    try:
        save_record(
            source="slack",
            route=route,
            extracted_text=extracted_text,
            description=description,
        )
    except Exception:
        logger.exception("Slack OCR 이력 저장 실패(응답에는 영향 없음)")


async def process_file(filename: str, file_bytes: bytes, lang: str = "kor+eng") -> str:
    """업로드 파일 확장자로 core 의 적절한 처리 함수를 호출하고, 사람이 읽을 응답 텍스트를 반환한다.

    Raises:
        ValueError: 지원하지 않는 포맷이거나 처리 중 오류
    """
    name = filename.lower()

    if name.endswith(".pdf"):
        result = await process_pdf(file_bytes, lang=lang)
        _save_record_safely(route="pdf_document", extracted_text=result.combined_text,
                             description=f"{result.page_count}페이지")
        return f"[PDF 인식 — {result.page_count}페이지]\n{result.combined_text}"

    if name.endswith(_VIDEO_EXTS):
        result = await process_video(file_bytes, lang=lang)
        _save_record_safely(route="video_frames", extracted_text=result.combined_text,
                             description=f"{len(result.document_frames)}개 텍스트 프레임")
        return f"[동영상 인식 — {len(result.document_frames)}개 프레임]\n{result.combined_text}"

    if name.endswith(".pptx"):
        result = await process_pptx(file_bytes)
        _save_record_safely(route="pptx_slides", extracted_text=result.combined_text,
                             description=f"{result.slide_count}슬라이드")
        return f"[PPTX 인식 — {result.slide_count}슬라이드]\n{result.combined_text}"

    if name.endswith(".docx"):
        result = await process_docx(file_bytes, lang=lang)
        _save_record_safely(route="docx_document", extracted_text=result.combined_text,
                             description=f"{result.paragraph_count}개 단락/행")
        return f"[DOCX 인식]\n{result.combined_text}"

    if name.endswith(".hwp"):
        result = process_hwp(file_bytes)
        _save_record_safely(route="hwp_document", extracted_text=result.combined_text,
                             description="HWP 문서 처리")
        return f"[HWP 인식]\n{result.combined_text}"

    if name.endswith(_IMAGE_EXTS):
        result = await process_image(file_bytes, lang=lang)
        if result.route in ("photo", "ambiguous_photo"):
            return f"[사진으로 인식 — 설명 기능은 준비 중]\n{result.note or ''}"
        _save_record_safely(route=result.route, extracted_text=result.text, description=None)
        return f"[문서로 인식]\n{result.text or '(텍스트 없음)'}"

    raise ValueError(f"지원하지 않는 파일 형식입니다: {filename}")
