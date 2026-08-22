"""Tesseract OCR provider — core/ocr/provider_base.OcrProvider 의 기본 구현체.

core/ocr/engine.py 의 기존 extract_text() 를 behavior-preserving 하게 감싼다(재발명 없음).
"""

from core.ocr.engine import extract_text


class TesseractProvider:
    def extract_text(self, image_bytes: bytes, lang: str = "kor+eng") -> str:
        return extract_text(image_bytes, lang=lang)
