"""PDF 페이지별 이미지 렌더링 + 기존 파이프라인 재사용.

PDF 각 페이지를 이미지로 렌더링(poppler/pdf2image) 후 telegram_bot.pipeline.process_image 에
그대로 태운다(code-structure.md §7 — 분류/OCR 로직 재발명 금지). 페이지 내부의 스캔된 서명·손글씨
등은 페이지 전체를 이미지로 취급하는 것으로 자동 커버되므로 별도 임베디드-이미지 추출은 하지 않는다.
"""

import io
import logging
from dataclasses import dataclass

from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError

from core.pipeline import PipelineResult, process_image

logger = logging.getLogger(__name__)

# 과도한 렌더링 방지(과설계/자원낭비 방지 — 긴 문서 대비 상한)
MAX_PDF_PAGES = 30
PDF_RENDER_DPI = 200


class UnsupportedPdfError(ValueError):
    """PDF 파일을 열 수 없거나 페이지가 없는 경우"""


@dataclass
class PdfPageResult:
    page_number: int
    pipeline_result: PipelineResult


@dataclass
class PdfOcrResult:
    page_count: int
    pages: list[PdfPageResult]
    combined_text: str


def _render_pages(pdf_bytes: bytes) -> list:
    try:
        pages = convert_from_bytes(pdf_bytes, dpi=PDF_RENDER_DPI, fmt="png")
    except (PDFPageCountError, PDFSyntaxError) as exc:
        raise UnsupportedPdfError("PDF 파일을 열 수 없습니다.") from exc

    if not pages:
        raise UnsupportedPdfError("PDF에서 페이지를 찾을 수 없습니다.")

    if len(pages) > MAX_PDF_PAGES:
        logger.warning(
            "PDF 페이지 수(%d)가 상한(%d)을 초과해 앞 %d페이지만 처리합니다.",
            len(pages), MAX_PDF_PAGES, MAX_PDF_PAGES,
        )
        pages = pages[:MAX_PDF_PAGES]

    return pages


async def process_pdf(pdf_bytes: bytes, lang: str = "kor+eng") -> PdfOcrResult:
    """PDF 를 페이지별로 렌더링해 기존 process_image 파이프라인으로 처리한다.

    Args:
        pdf_bytes: PDF 원본 바이트
        lang: tesseract 언어 코드

    Returns:
        PdfOcrResult: 페이지별 결과 + 전체 텍스트를 페이지 구분자로 이어붙인 combined_text

    Raises:
        UnsupportedPdfError: PDF 를 열 수 없거나 페이지가 없는 경우
    """
    pages = _render_pages(pdf_bytes)

    page_results: list[PdfPageResult] = []
    text_chunks: list[str] = []

    for idx, page_image in enumerate(pages, start=1):
        buf = io.BytesIO()
        page_image.save(buf, format="PNG")
        page_bytes = buf.getvalue()

        result = await process_image(page_bytes, lang=lang)
        page_results.append(PdfPageResult(page_number=idx, pipeline_result=result))

        if result.text:
            text_chunks.append(f"[페이지 {idx}]\n{result.text}")
        elif result.note:
            text_chunks.append(f"[페이지 {idx}] {result.note}")

    combined_text = "\n\n".join(text_chunks)
    return PdfOcrResult(page_count=len(pages), pages=page_results, combined_text=combined_text)
