"""OCR 원본 텍스트로부터 문서 유형(영수증·명함·일반문서)을 판별한다.

키워드 휴리스틱을 먼저 시도하고, 애매하면 로컬 MLX 모델에게 짧게 물어보는 폴백 방식을 쓴다
(완벽한 분류기가 목표가 아니라, structure_text() 의 doc_type="auto" 호출을 자동 라우팅하기 위한
가벼운 1차 판별기). 모델 로드/추론은 core.ocr.structurer 의 기존 전역 캐시(_load_model)를 그대로
재사용한다 — 재로드 없음.
"""

import logging
import re

logger = logging.getLogger(__name__)

DocType = str  # "receipt" | "card" | "auto"

_RECEIPT_KEYWORDS = ("영수증", "합계", "총액", "결제", "카드승인", "부가세", "받은금액")
_CARD_TITLE_KEYWORDS = ("대표", "이사", "부장", "차장", "과장", "팀장", "매니저", "사원", "대리")
_PHONE_PATTERN = re.compile(r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}")
_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

_FALLBACK_PROMPT_TEMPLATE = (
    "다음 텍스트가 영수증(receipt), 명함(card), 일반 문서(auto) 중 어느 것에 가장 가까운지 "
    "한 단어로만 답하라(receipt/card/auto 중 하나만 출력, 다른 설명 금지).\n\n"
    "텍스트:\n{raw_text}\n\n답:"
)


def _keyword_guess(raw_text: str) -> DocType | None:
    """키워드 휴리스틱으로 1차 판별을 시도한다. 확신이 없으면 None을 반환해 폴백을 유도한다."""
    if any(kw in raw_text for kw in _RECEIPT_KEYWORDS):
        return "receipt"

    has_phone = bool(_PHONE_PATTERN.search(raw_text))
    has_email = bool(_EMAIL_PATTERN.search(raw_text))
    has_title = any(kw in raw_text for kw in _CARD_TITLE_KEYWORDS)
    if has_phone and (has_email or has_title):
        return "card"

    return None


def _mlx_guess(raw_text: str) -> DocType:
    """키워드로 확신이 안 설 때 MLX 모델에게 짧게 물어본다(기존 캐시된 모델 재사용, 재로드 없음)."""
    # 순환 import 방지를 위해 함수 내부에서 지연 import(structurer.py 가 이 모듈을 참조하지 않으므로
    # 안전하지만, 모듈 로드 순서에 안전 마진을 둔다).
    from core.ocr.structurer import StructurerNotConfiguredError, _load_model

    try:
        from mlx_lm import generate

        model, tokenizer = _load_model()
    except StructurerNotConfiguredError:
        logger.warning("MLX 모델 미설정 — 문서유형 폴백 판별 불가, auto 로 처리")
        return "auto"

    prompt = _FALLBACK_PROMPT_TEMPLATE.format(raw_text=raw_text[:1500])
    messages = [{"role": "user", "content": prompt}]
    formatted = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)

    try:
        response = generate(model, tokenizer, prompt=formatted, max_tokens=8, verbose=False)
    except Exception:  # noqa: BLE001
        logger.exception("문서유형 MLX 폴백 추론 실패 — auto 로 처리")
        return "auto"

    normalized = response.strip().lower()
    for candidate in ("receipt", "card", "auto"):
        if candidate in normalized:
            return candidate
    return "auto"


def detect_doc_type(raw_text: str) -> DocType:
    """OCR 원본 텍스트로부터 문서 유형을 판별한다.

    1차: 키워드 휴리스틱(영수증 키워드, 전화번호+이메일/직함 조합) — 비용 없음.
    2차(폴백): 1차로 확신이 안 설 때만 MLX 모델에게 짧게 질의(모델은 기존 전역 캐시 재사용).

    Args:
        raw_text: OCR/파서로 추출한 원본 텍스트

    Returns:
        "receipt" | "card" | "auto"
    """
    if not raw_text or not raw_text.strip():
        return "auto"

    guess = _keyword_guess(raw_text)
    if guess is not None:
        return guess

    return _mlx_guess(raw_text)
