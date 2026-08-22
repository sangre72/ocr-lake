"""Tesseract OcrProvider 어댑터 — 기존 core/ocr/engine.py 를 OcrProvider 인터페이스로 감싼다.

behavior-preserving: engine.py 의 실제 로직은 그대로 두고 얇게 위임만 한다(재발명 금지,
core/storage/sqlite_provider.py 와 동일한 어댑터 패턴).
"""

from core.classify.engine import _load_image, _text_signal
from core.ocr.engine import extract_text
from core.ocr.provider_base import OcrProviderResult


class TesseractProvider:
    def extract_text(self, image_bytes: bytes, lang: str = "kor+eng") -> OcrProviderResult:
        text = extract_text(image_bytes, lang=lang)
        # confidence 는 core/classify/engine.py 가 이미 계산하는 로직을 재사용(재발명 금지)
        image = _load_image(image_bytes)
        _, avg_conf = _text_signal(image, lang)
        return OcrProviderResult(text=text, confidence=avg_conf)
