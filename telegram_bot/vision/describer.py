"""사진(텍스트 희박 이미지) 설명 모듈.

AI 비전 모델(Claude/GPT 등) 연동은 추후 결정 — 현재는 미구현 스텁.
structurer.py 와 동일 패턴: 모델 결정되면 이 모듈 안에서 SDK 호출부만 구현하면 되고,
pipeline/handlers 쪽은 변경 불요.
"""


class DescriberNotConfiguredError(RuntimeError):
    """이미지 설명용 AI 비전 모델이 아직 설정되지 않음"""


async def image_describe(image_bytes: bytes) -> str:
    """이미지(텍스트가 거의 없는 사진)를 설명 텍스트로 변환한다.

    Args:
        image_bytes: 이미지 원본 바이트

    Returns:
        이미지 설명 텍스트

    Raises:
        DescriberNotConfiguredError: AI 비전 모델 연동 미설정 시

    TODO: ANTHROPIC_API_KEY/OPENAI_API_KEY 등 비전 모델 연동 확정 후 구현.
    """
    raise DescriberNotConfiguredError(
        "이미지 설명용 AI 비전 모델이 아직 설정되지 않았습니다. "
        "ANTHROPIC_API_KEY 또는 OPENAI_API_KEY 설정 후 구현 예정."
    )
