"""OCR 원본 텍스트 → 구조화 데이터(영수증·명함 등) 변환.

AI 모델(Claude/GPT 등) 연동은 추후 결정 — 현재는 미구현 스텁.
결정되면 이 모듈에서 해당 SDK 호출부만 구현하면 되고, handlers 쪽은 변경 불요.
"""


class StructurerNotConfiguredError(RuntimeError):
    """AI 구조화 모델이 아직 설정되지 않음"""


async def structure_text(raw_text: str, doc_type: str = "auto") -> dict:
    """OCR 원본 텍스트를 구조화된 필드(dict)로 변환한다.

    Args:
        raw_text: extract_text() 로 얻은 원본 텍스트
        doc_type: "receipt" | "card" | "auto" 등 문서 유형 힌트

    Returns:
        구조화된 필드 dict

    Raises:
        StructurerNotConfiguredError: AI 모델 연동 미설정 시
    """
    raise StructurerNotConfiguredError(
        "구조화 파싱용 AI 모델이 아직 설정되지 않았습니다. "
        "ANTHROPIC_API_KEY 또는 OPENAI_API_KEY 설정 후 구현 예정."
    )
