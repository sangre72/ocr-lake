"""Slack 봇 설정 모듈 (telegram_bot/config.py 와 대칭 패턴)"""

import os
from dataclasses import dataclass


@dataclass
class SlackConfig:
    bot_token: str
    signing_secret: str
    allowed_channel_ids: list[str]
    ocr_lang: str = "kor+eng"
    max_file_size_mb: int = 20
    port: int = 3010


def load_config() -> SlackConfig:
    """환경변수에서 Slack 봇 설정을 로드합니다.

    필수 환경변수:
        SLACK_BOT_TOKEN: Slack 봇 토큰(xoxb-...)
        SLACK_SIGNING_SECRET: Slack 앱 서명 시크릿(이벤트 검증용)
        SLACK_ALLOWED_CHANNEL_IDS: 허용된 채널 ID 목록(쉼표 구분, 비어있으면 전체 허용)

    Raises:
        ValueError: SLACK_BOT_TOKEN 또는 SLACK_SIGNING_SECRET이 설정되지 않은 경우
    """
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN 환경변수가 설정되지 않았습니다.")
    if not signing_secret:
        raise ValueError("SLACK_SIGNING_SECRET 환경변수가 설정되지 않았습니다.")

    raw_ids = os.environ.get("SLACK_ALLOWED_CHANNEL_IDS", "").strip()
    allowed_channel_ids = [p.strip() for p in raw_ids.split(",") if p.strip()] if raw_ids else []

    return SlackConfig(
        bot_token=bot_token,
        signing_secret=signing_secret,
        allowed_channel_ids=allowed_channel_ids,
        ocr_lang=os.environ.get("SLACK_OCR_LANG", "kor+eng"),
        max_file_size_mb=int(os.environ.get("SLACK_MAX_FILE_SIZE_MB", "20")),
        port=int(os.environ.get("SLACK_PORT", "3010")),
    )
