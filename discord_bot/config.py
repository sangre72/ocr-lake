"""Discord 봇 설정 모듈 (telegram_bot/config.py 와 대칭 패턴)"""

import os
from dataclasses import dataclass


@dataclass
class DiscordConfig:
    token: str
    allowed_channel_ids: list[int]
    ocr_lang: str = "kor+eng"
    max_file_size_mb: int = 20


def load_config() -> DiscordConfig:
    """환경변수에서 Discord 봇 설정을 로드합니다.

    필수 환경변수:
        DISCORD_BOT_TOKEN: Discord 봇 토큰
        DISCORD_ALLOWED_CHANNEL_IDS: 허용된 채널 ID 목록(쉼표 구분, 비어있으면 전체 허용)

    Raises:
        ValueError: DISCORD_BOT_TOKEN이 설정되지 않은 경우
    """
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN 환경변수가 설정되지 않았습니다.")

    raw_ids = os.environ.get("DISCORD_ALLOWED_CHANNEL_IDS", "").strip()
    allowed_channel_ids: list[int] = []
    if raw_ids:
        for part in raw_ids.split(","):
            part = part.strip()
            if part:
                try:
                    allowed_channel_ids.append(int(part))
                except ValueError:
                    pass

    return DiscordConfig(
        token=token,
        allowed_channel_ids=allowed_channel_ids,
        ocr_lang=os.environ.get("DISCORD_OCR_LANG", "kor+eng"),
        max_file_size_mb=int(os.environ.get("DISCORD_MAX_FILE_SIZE_MB", "20")),
    )
