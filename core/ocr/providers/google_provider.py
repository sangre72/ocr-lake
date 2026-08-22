"""Google Cloud Vision OCR Provider — REST API 직접 호출(SDK 미사용).

★설계 결정: `google-cloud-vision` 공식 SDK는 설치 시 이 머신의 시스템 전역 `protobuf`를 7.x로
강제 업그레이드해 다른 프로젝트(tensorflow 등, protobuf<6.0 요구)를 깨뜨리는 의존성 충돌이 실측
확인되어 채택하지 않았다(a_19 RAG 실패와 같은 패턴 — 신규 대형 패키지가 시스템 전역을 오염시키는
사고 재발 방지). 대신 Google Vision REST API(`vision.googleapis.com`)를 API 키만으로 직접 호출하는
방식을 채택했다 — 이미 설치된 `requests`만 사용하므로 신규 의존성 0.
"""

import base64
import os

import requests

from core.ocr.provider_base import OcrProviderResult

_API_URL = "https://vision.googleapis.com/v1/images:annotate"
_TIMEOUT_SEC = 30


class GoogleVisionNotConfiguredError(RuntimeError):
    """GOOGLE_CLOUD_VISION_API_KEY 환경변수가 설정되지 않음"""


class GoogleVisionApiError(RuntimeError):
    """Google Vision API 호출 실패(네트워크 오류, API 응답 오류 등)"""


class GoogleVisionProvider:
    def extract_text(self, image_bytes: bytes, lang: str = "kor+eng") -> OcrProviderResult:
        api_key = os.environ.get("GOOGLE_CLOUD_VISION_API_KEY", "").strip()
        if not api_key:
            raise GoogleVisionNotConfiguredError(
                "GOOGLE_CLOUD_VISION_API_KEY 환경변수가 설정되지 않았습니다. "
                "Google Cloud Console에서 Vision API 키를 발급해 .env 에 설정하세요."
            )

        content_b64 = base64.b64encode(image_bytes).decode("ascii")
        # lang(예: "kor+eng")을 Vision API 언어 힌트로 매핑(간단 변환 — 정확한 매핑은 필요시 확장)
        language_hints = [code for code in lang.replace("eng", "en").split("+") if code]

        payload = {
            "requests": [
                {
                    "image": {"content": content_b64},
                    "features": [{"type": "TEXT_DETECTION"}],
                    "imageContext": {"languageHints": language_hints} if language_hints else {},
                }
            ]
        }

        try:
            resp = requests.post(
                f"{_API_URL}?key={api_key}", json=payload, timeout=_TIMEOUT_SEC
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise GoogleVisionApiError(f"Google Vision API 호출에 실패했습니다: {exc}") from exc

        data = resp.json()
        result = data.get("responses", [{}])[0]
        if "error" in result:
            raise GoogleVisionApiError(f"Google Vision API 오류: {result['error']}")

        annotations = result.get("textAnnotations", [])
        text = annotations[0]["description"].strip() if annotations else ""
        # 전체 텍스트 어노테이션에는 confidence 가 없는 경우가 많음(TEXT_DETECTION 특성) — None 반환
        return OcrProviderResult(text=text, confidence=None)
