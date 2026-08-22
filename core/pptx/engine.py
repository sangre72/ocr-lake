"""PowerPoint(.pptx) 슬라이드 텍스트 추출.

슬라이드 안의 텍스트박스는 이미 구조화된 텍스트라 python-pptx로 직접 읽으면 OCR 없이도 정확도 100%다
(code-structure.md §7 — 이미 구조화된 데이터를 OCR로 우회 추출하지 않는다).

★1차 구현 범위: 텍스트박스 텍스트 직접 추출만. 슬라이드 안에 이미지로 삽입된 텍스트(스크린샷 붙여넣기 등)는
이번 스코프에서 제외한다 — LibreOffice headless 등 슬라이드→이미지 렌더링 도구는 설치 부담이 커서
(network-budget.md) 1차 구현에 포함하지 않았다. 필요성이 확인되면 후속 작업으로 core/pdf/engine.py 와
유사하게 렌더링→process_image 재사용 방식을 추가할 수 있다.
"""

import io
import logging
from dataclasses import dataclass

from pptx import Presentation
from pptx.exc import PackageNotFoundError

logger = logging.getLogger(__name__)

# 과도한 처리 방지(과설계/자원낭비 방지 — core/pdf 의 MAX_PDF_PAGES 와 동일 취지)
MAX_SLIDES = 100


class UnsupportedPptxError(ValueError):
    """PPTX 파일을 열 수 없거나 슬라이드가 없는 경우"""


@dataclass
class PptxSlideResult:
    slide_number: int
    text: str


@dataclass
class PptxOcrResult:
    slide_count: int
    slides: list[PptxSlideResult]
    combined_text: str


def _extract_slide_text(slide) -> str:
    """슬라이드 내 모든 텍스트프레임의 텍스트를 순서대로 이어붙인다."""
    chunks: list[str] = []
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        text = shape.text_frame.text
        if text.strip():
            chunks.append(text)
    return "\n".join(chunks)


async def process_pptx(pptx_bytes: bytes, lang: str = "kor+eng") -> PptxOcrResult:
    """PPTX 슬라이드별 텍스트박스 텍스트를 추출한다.

    Args:
        pptx_bytes: PPTX 원본 바이트
        lang: 다른 process_* 함수와 시그니처 일관성을 위해 유지(텍스트 직접 추출이라 실제 미사용)

    Returns:
        PptxOcrResult: 슬라이드별 결과 + "[슬라이드 N]\\n텍스트" 형태로 이어붙인 combined_text

    Raises:
        UnsupportedPptxError: PPTX 를 열 수 없거나 슬라이드가 없는 경우
    """
    try:
        presentation = Presentation(io.BytesIO(pptx_bytes))
    except PackageNotFoundError as exc:
        raise UnsupportedPptxError("PPTX 파일을 열 수 없습니다.") from exc
    except Exception as exc:
        raise UnsupportedPptxError("PPTX 파일을 열 수 없습니다.") from exc

    slides = list(presentation.slides)
    if not slides:
        raise UnsupportedPptxError("PPTX에서 슬라이드를 찾을 수 없습니다.")

    if len(slides) > MAX_SLIDES:
        logger.warning(
            "PPTX 슬라이드 수(%d)가 상한(%d)을 초과해 앞 %d개만 처리합니다.",
            len(slides), MAX_SLIDES, MAX_SLIDES,
        )
        slides = slides[:MAX_SLIDES]

    slide_results: list[PptxSlideResult] = []
    text_chunks: list[str] = []

    for idx, slide in enumerate(slides, start=1):
        text = _extract_slide_text(slide)
        slide_results.append(PptxSlideResult(slide_number=idx, text=text))
        if text:
            text_chunks.append(f"[슬라이드 {idx}]\n{text}")

    combined_text = "\n\n".join(text_chunks)
    return PptxOcrResult(slide_count=len(slides), slides=slide_results, combined_text=combined_text)
