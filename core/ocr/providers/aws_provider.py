"""AWS Textract OCR Provider — 인터페이스만 준비(실구현 아님).

★스코프 판단(a_21): 이 레포 .env 어디에도 AWS 자격증명이 없음을 실측 확인(2026-08-22).
자격증명이 확보되면 boto3(textract client)로 실구현 예정 — 지금은 호출 시 명확한 미구현
에러만 낸다(network-budget.md — boto3 미설치, 실구현 전까지 SDK 설치 보류).
"""

from core.ocr.provider_base import OcrProviderResult


class AwsTextractNotImplementedError(NotImplementedError):
    """AWS Textract provider 미구현(자격증명 미확보 — 인터페이스만 준비된 상태)"""


class AwsTextractProvider:
    def extract_text(self, image_bytes: bytes, lang: str = "kor+eng") -> OcrProviderResult:
        raise AwsTextractNotImplementedError(
            "AWS Textract provider 는 아직 구현되지 않았습니다(자격증명 미확보, boto3 미설치). "
            "AWS 자격증명이 확보되면 실구현 예정 — docs/tech-spec.md §14-4 참고."
        )
