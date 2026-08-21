"""텔레그램 봇 설정 모듈"""

import os
from dataclasses import dataclass


@dataclass
class BotConfig:
    token: str
    allowed_chat_ids: list[int]
    ocr_lang: str = "kor+eng"
    max_image_size_mb: int = 20


def load_config() -> BotConfig:
    """환경변수에서 봇 설정을 로드합니다.

    필수 환경변수:
        TELEGRAM_BOT_TOKEN: 텔레그램 봇 토큰
        TELEGRAM_ALLOWED_CHAT_IDS: 허용된 채팅 ID 목록 (쉼표 구분, 비어있으면 전체 허용)

    Returns:
        BotConfig: 봇 설정 객체

    Raises:
        ValueError: TELEGRAM_BOT_TOKEN이 설정되지 않은 경우
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다."
        )

    raw_ids = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").strip()
    allowed_chat_ids: list[int] = []
    if raw_ids:
        for part in raw_ids.split(","):
            part = part.strip()
            if part:
                try:
                    allowed_chat_ids.append(int(part))
                except ValueError:
                    pass

    return BotConfig(
        token=token,
        allowed_chat_ids=allowed_chat_ids,
        ocr_lang=os.environ.get("TELEGRAM_OCR_LANG", "kor+eng"),
        max_image_size_mb=int(
            os.environ.get("TELEGRAM_MAX_IMAGE_SIZE_MB", "20")
        ),
    )
