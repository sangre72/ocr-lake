"""OCR 원본 텍스트 → 구조화 데이터(영수증·명함 등) 변환.

로컬 MLX(Apple Silicon 네이티브 가속, mlx-lm) 로 텍스트 전용 LLM 을 구동해 문서 유형별 스키마로
구조화한다. 비전 모델은 불필요(입력은 이미 OCR로 추출된 텍스트) — 로드맵 §14-2(이미지 설명)와는 별개 스코프.

Ollama 대신 MLX 채택 이유: docs/planning/standards/local-model-selection.md 참고
(Apple Silicon 네이티브 Metal 가속 → 동일 4bit 양자화 모델 기준 체감 속도 우수).
"""

import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

MLX_MODEL_ID = os.environ.get("MLX_STRUCTURER_MODEL", "mlx-community/Qwen2.5-7B-Instruct-4bit")
MAX_TOKENS = 512

_DOC_TYPE_SCHEMAS: dict[str, dict] = {
    "receipt": {"merchant": "str", "date": "str", "items": [{"name": "str", "price": "number"}], "total": "number"},
    "card": {"name": "str", "company": "str", "title": "str", "phone": "str", "email": "str", "address": "str"},
    "auto": {"summary": "str", "keyFields": {"key": "value"}},
}

# 모델 로드는 무겁다(수 초~수십 초) — 프로세스당 1회만 로드해 재사용(모듈 전역 캐시).
_model = None
_tokenizer = None
_load_lock = threading.Lock()


class StructurerNotConfiguredError(RuntimeError):
    """로컬 MLX 모델을 로드하거나 응답을 파싱할 수 없는 경우"""


def _load_model():
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer
    with _load_lock:
        if _model is not None:
            return _model, _tokenizer
        try:
            from mlx_lm import load
        except ImportError as exc:
            raise StructurerNotConfiguredError(
                "mlx-lm 패키지가 설치되어 있지 않습니다. `pip install mlx-lm` 필요."
            ) from exc
        try:
            _model, _tokenizer = load(MLX_MODEL_ID)
        except Exception as exc:  # noqa: BLE001
            raise StructurerNotConfiguredError(
                f"MLX 모델({MLX_MODEL_ID}) 로드에 실패했습니다: {exc}"
            ) from exc
    return _model, _tokenizer


def _build_prompt(raw_text: str, doc_type: str) -> str:
    schema = _DOC_TYPE_SCHEMAS.get(doc_type, _DOC_TYPE_SCHEMAS["auto"])
    schema_json = json.dumps(schema, ensure_ascii=False)
    return (
        "다음은 OCR로 추출한 원본 텍스트다. 아래 JSON 스키마 형태로만 응답하라. "
        "다른 설명 문장 없이 JSON 객체 하나만 출력하라.\n\n"
        f"스키마 예시: {schema_json}\n\n"
        f"원본 텍스트:\n{raw_text}\n\n"
        "JSON:"
    )


def _extract_json(raw_response: str) -> dict:
    """모델 응답에서 JSON 객체만 추출한다(모델이 코드블록·설명을 덧붙이는 경우 대비)."""
    text = raw_response.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise StructurerNotConfiguredError("모델 응답에서 JSON을 찾을 수 없습니다.")
    return json.loads(text[start : end + 1])


async def structure_text(raw_text: str, doc_type: str = "auto") -> dict:
    """OCR 원본 텍스트를 구조화된 필드(dict)로 변환한다.

    Args:
        raw_text: extract_text() 로 얻은 원본 텍스트
        doc_type: "receipt" | "card" | "auto" 등 문서 유형 힌트

    Returns:
        구조화된 필드 dict

    Raises:
        StructurerNotConfiguredError: 모델 로드 실패·응답 파싱 실패 시
    """
    if not raw_text or not raw_text.strip():
        raise StructurerNotConfiguredError("구조화할 텍스트가 비어 있습니다.")

    from mlx_lm import generate

    model, tokenizer = _load_model()
    prompt = _build_prompt(raw_text, doc_type)
    messages = [{"role": "user", "content": prompt}]
    formatted = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)

    try:
        model_text = generate(model, tokenizer, prompt=formatted, max_tokens=MAX_TOKENS, verbose=False)
    except Exception as exc:  # noqa: BLE001
        logger.exception("MLX 모델 추론 실패")
        raise StructurerNotConfiguredError(f"모델 추론 중 오류가 발생했습니다: {exc}") from exc

    try:
        return _extract_json(model_text)
    except (json.JSONDecodeError, StructurerNotConfiguredError) as exc:
        logger.warning("구조화 응답 파싱 실패: %s", model_text[:200])
        raise StructurerNotConfiguredError(
            "모델 응답을 구조화된 JSON으로 파싱하지 못했습니다."
        ) from exc
