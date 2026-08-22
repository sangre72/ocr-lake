"""OCR Provider 추상 인터페이스.

향후 클라우드 OCR(AWS Textract, Azure Document Intelligence, Naver CLOVA, Google Vision 등)을
추가할 때 이 Protocol만 구현하면 된다. 지금은 TesseractProvider 하나만 등록돼 있다.
core/storage/base.py 의 StorageProvider 패턴과 동일 구조.
"""

from typing import Protocol


class OcrProvider(Protocol):
    def extract_text(self, image_bytes: bytes, lang: str = "kor+eng") -> str:
        ...
