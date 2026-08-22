"""OCR Provider 추상 인터페이스.

향후 다른 OCR 백엔드(AWS Textract, Azure Document Intelligence, Naver CLOVA OCR, Google Cloud
Vision 등)를 추가할 때 이 Protocol만 구현하면 된다(core/storage/base.py 의 StorageProvider 패턴과
동일 구조 — code-structure.md §4). 기존 core/ocr/engine.py(Tesseract)가 기본 구현체다.
"""

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class OcrProviderResult:
    text: str
    confidence: Optional[float] = None  # 0~100, provider 가 confidence 를 제공하지 않으면 None


class OcrProvider(Protocol):
    def extract_text(self, image_bytes: bytes, lang: str = "kor+eng") -> OcrProviderResult:
        """이미지에서 텍스트를 추출한다.

        Raises:
            해당 provider 고유의 예외(예: 자격증명 없음, API 오류) — 호출부가 잡아 폴백 판단.
        """
        ...
