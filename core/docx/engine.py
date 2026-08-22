"""Word(.docx) 문단·표 텍스트 추출.

.docx(OOXML)는 python-docx로 직접 읽으면 이미 구조화된 텍스트라 OCR이 필요 없다
(core/pptx/engine.py, core/hwp/engine.py 와 동일 원칙 — code-structure.md §7).

★레거시 .doc(구 바이너리 포맷)은 이번 스코프에서 제외한다: antiword/catdoc(시스템 바이너리)·textract
(유지보수 중단) 등 후보를 검토했으나 이 환경에 설치돼 있지 않고, 별도 시스템 패키지 설치가 필요해
network-budget.md 관점에서 무리하게 밀어붙이지 않았다. 필요성이 확인되면 별도 작업으로 검토.
"""

import io
import logging
from dataclasses import dataclass

from docx import Document
from docx.opc.exceptions import PackageNotFoundError

logger = logging.getLogger(__name__)

# 과도한 처리 방지(core/pdf 의 MAX_PDF_PAGES, core/pptx 의 MAX_SLIDES 와 동일 취지)
MAX_PARAGRAPHS = 2000


class UnsupportedDocxError(ValueError):
    """DOCX 파일을 열 수 없거나 텍스트가 없는 경우"""


@dataclass
class DocxOcrResult:
    paragraph_count: int
    combined_text: str


def _extract_text(document: Document) -> list[str]:
    chunks: list[str] = []

    for para in document.paragraphs:
        if para.text.strip():
            chunks.append(para.text)

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                chunks.append(" | ".join(cells))

    return chunks


async def process_docx(docx_bytes: bytes, lang: str = "kor+eng") -> DocxOcrResult:
    """DOCX 문단·표 텍스트를 직접 추출한다.

    Args:
        docx_bytes: DOCX 원본 바이트
        lang: 다른 process_* 함수와 시그니처 일관성을 위해 유지(텍스트 직접 추출이라 실제 미사용)

    Returns:
        DocxOcrResult: 문단 수 + 이어붙인 combined_text

    Raises:
        UnsupportedDocxError: DOCX 를 열 수 없거나 텍스트가 없는 경우
    """
    try:
        document = Document(io.BytesIO(docx_bytes))
    except PackageNotFoundError as exc:
        raise UnsupportedDocxError("DOCX 파일을 열 수 없습니다.") from exc
    except Exception as exc:
        raise UnsupportedDocxError("DOCX 파일을 열 수 없습니다.") from exc

    chunks = _extract_text(document)
    if len(chunks) > MAX_PARAGRAPHS:
        logger.warning(
            "DOCX 문단/표 수(%d)가 상한(%d)을 초과해 앞부분만 처리합니다.",
            len(chunks), MAX_PARAGRAPHS,
        )
        chunks = chunks[:MAX_PARAGRAPHS]

    if not chunks:
        raise UnsupportedDocxError("DOCX에서 텍스트를 찾을 수 없습니다.")

    combined_text = "\n".join(chunks)
    return DocxOcrResult(paragraph_count=len(chunks), combined_text=combined_text)
