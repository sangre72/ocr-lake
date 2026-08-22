"""사진(텍스트 희박 이미지) 설명 모듈.

로컬 MLX 비전-언어 모델(mlx-vlm, Apple Silicon 네이티브 가속)로 이미지를 설명한다.
core/ocr/structurer.py 와 동일 패턴(모듈 전역 캐시, 로컬 모델 재사용, 신규 다운로드 최소화).

★텍스트 전용 모델을 억지로 비전 용도에 전용하지 않는다 — 실제 비전-언어 모델(mlx-vlm +
mlx-community/Qwen2.5-VL-7B-Instruct-4bit, 로컬에 이미 캐시돼 있어 재다운로드 없음)을 사용한다.
"""

import io
import logging
import os
import threading

from PIL import Image

logger = logging.getLogger(__name__)

VLM_MODEL_ID = os.environ.get("MLX_VISION_MODEL", "mlx-community/Qwen2.5-VL-7B-Instruct-4bit")
MAX_TOKENS = 200

_model = None
_processor = None
_config = None
_load_lock = threading.Lock()


class DescriberNotConfiguredError(RuntimeError):
    """비전 모델을 로드하거나 추론할 수 없는 경우"""


def _load_model():
    global _model, _processor, _config
    if _model is not None:
        return _model, _processor, _config
    with _load_lock:
        if _model is not None:
            return _model, _processor, _config
        try:
            from mlx_vlm import load
            from mlx_vlm.utils import load_config
        except ImportError as exc:
            raise DescriberNotConfiguredError(
                "mlx-vlm 패키지가 설치되어 있지 않습니다. `pip install mlx-vlm` 필요."
            ) from exc
        try:
            _model, _processor = load(VLM_MODEL_ID)
            _config = load_config(VLM_MODEL_ID)
        except Exception as exc:  # noqa: BLE001
            raise DescriberNotConfiguredError(
                f"비전 모델({VLM_MODEL_ID}) 로드에 실패했습니다: {exc}"
            ) from exc
    return _model, _processor, _config


async def image_describe(image_bytes: bytes) -> str:
    """이미지(텍스트가 거의 없는 사진)를 설명 텍스트로 변환한다.

    Args:
        image_bytes: 이미지 원본 바이트

    Returns:
        이미지 설명 텍스트

    Raises:
        DescriberNotConfiguredError: 비전 모델 로드 실패·추론 실패 시
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception as exc:  # noqa: BLE001
        raise DescriberNotConfiguredError("이미지 파일을 열 수 없습니다.") from exc

    from mlx_vlm import generate
    from mlx_vlm.prompt_utils import apply_chat_template

    model, processor, config = _load_model()
    prompt = apply_chat_template(
        processor, config, "이 이미지에 무엇이 있는지 한국어로 간단히 설명하라.", num_images=1
    )

    try:
        result = generate(model, processor, prompt, [image], max_tokens=MAX_TOKENS, verbose=False)
    except Exception as exc:  # noqa: BLE001
        logger.exception("비전 모델 추론 실패")
        raise DescriberNotConfiguredError(f"이미지 설명 추론 중 오류가 발생했습니다: {exc}") from exc

    return result.text.strip()
