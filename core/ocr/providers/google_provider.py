"""Google Cloud Vision OCR provider.

network-budget.md 준수: 이 레포의 .env 어디에도 클라우드 자격증명(AWS/GCP/Azure/Naver)이 없음을
실측 확인했다(2026-08-22). 자격증명 발급 전까지는 라이브 API 호출이 불가하므로, 이 provider는
"코드는 완성하되 자격증명 없으면 명확한 에러"로 구현한다.

Google Cloud Vision 을 우선 구현 대상으로 선택한 이유(docs/research/ocr-technology-trends.md 참고):
API가 비교적 단순하고(서비스계정 JSON 키 1개), 무료 티어가 있다.
"""

import json
import os


class GoogleVisionCredentialsError(RuntimeError):
    """GOOGLE_APPLICATION_CREDENTIALS(서비스계정 키 경로) 또는 GOOGLE_VISION_API_KEY 가 미설정인 경우"""


class GoogleVisionProvider:
    def extract_text(self, image_bytes: bytes, lang: str = "kor+eng") -> str:
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        api_key = os.environ.get("GOOGLE_VISION_API_KEY", "").strip()
        if not cred_path and not api_key:
            raise GoogleVisionCredentialsError(
                "Google Cloud Vision 자격증명이 설정되지 않았습니다. "
                "GOOGLE_APPLICATION_CREDENTIALS(서비스계정 JSON 키 경로) 또는 "
                "GOOGLE_VISION_API_KEY 를 .env 에 설정한 뒤 다시 시도하세요."
            )

        try:
            from google.cloud import vision
        except ImportError as exc:
            raise GoogleVisionCredentialsError(
                "google-cloud-vision 패키지가 설치되어 있지 않습니다. `pip install google-cloud-vision` 필요."
            ) from exc

        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_bytes)
        response = client.text_detection(image=image)
        if response.error.message:
            raise RuntimeError(f"Google Vision API 오류: {response.error.message}")
        annotations = response.text_annotations
        return annotations[0].description.strip() if annotations else ""
