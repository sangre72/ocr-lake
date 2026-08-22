"""Naver CLOVA OCR Provider — 인터페이스만 준비(실구현 아님).

★스코프 판단(a_21): 이 레포 .env 어디에도 Naver Cloud Platform 자격증명이 없음을 실측
확인(2026-08-22)(AUTH_NAVER_* 는 a_61 소셜로그인용이라 무관 — 이 provider와 별개).
자격증명이 확보되면 CLOVA OCR REST API(requests 만으로 호출 가능, google_provider.py 와 동일
패턴)로 실구현 예정 — 지금은 호출 시 명확한 미구현 에러만 낸다.
"""

from core.ocr.provider_base import OcrProviderResult


class NaverClovaNotImplementedError(NotImplementedError):
    """Naver CLOVA OCR provider 미구현(자격증명 미확보 — 인터페이스만 준비된 상태)"""


class NaverClovaProvider:
    def extract_text(self, image_bytes: bytes, lang: str = "kor+eng") -> OcrProviderResult:
        raise NaverClovaNotImplementedError(
            "Naver CLOVA OCR provider 는 아직 구현되지 않았습니다(자격증명 미확보). "
            "Naver Cloud Platform 자격증명이 확보되면 실구현 예정 — docs/tech-spec.md §14-4 참고."
        )
