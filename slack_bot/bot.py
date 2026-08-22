"""Slack 봇(Bolt) 앱 생성 및 실행 (telegram_bot/bot.py 와 대칭 패턴).

토큰 로드·검증은 main()/run() 호출 시점에만 일어난다 — 모듈 임포트 자체는 토큰 없이도 가능하다.
"""

import asyncio
import logging

import requests
from dotenv import load_dotenv
from slack_bolt import App

from core.storage import init_db
from slack_bot.config import load_config
from slack_bot.handlers import is_allowed, process_file

load_dotenv(".env.local")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_REPLY_LIMIT = 3800  # Slack 메시지 실질 제한 여유 확보


def build_app(config) -> App:
    app = App(token=config.bot_token, signing_secret=config.signing_secret)

    @app.event("file_shared")
    def handle_file_shared(event, client, say):
        channel_id = event.get("channel_id", "")
        if not is_allowed(channel_id, config.allowed_channel_ids):
            return

        file_id = event.get("file_id")
        if not file_id:
            return

        file_info = client.files_info(file=file_id)["file"]
        filename = file_info.get("name", "")
        file_size_mb = file_info.get("size", 0) / (1024 * 1024)
        if file_size_mb > config.max_file_size_mb:
            say(channel=channel_id, text=f"파일이 너무 큽니다(최대 {config.max_file_size_mb}MB).")
            return

        url = file_info.get("url_private_download") or file_info.get("url_private")
        headers = {"Authorization": f"Bearer {config.bot_token}"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()

        try:
            reply = asyncio.run(process_file(filename, resp.content, lang=config.ocr_lang))
        except ValueError as exc:
            say(channel=channel_id, text=f"처리할 수 없습니다: {exc}")
            return
        except Exception:
            logger.exception("Slack 파일 처리 중 오류")
            say(channel=channel_id, text="처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
            return

        if len(reply) > _REPLY_LIMIT:
            reply = reply[:_REPLY_LIMIT] + "\n…(이하 생략)"
        say(channel=channel_id, text=reply)

    return app


def main() -> None:
    init_db()
    config = load_config()
    app = build_app(config)
    logger.info("ocr-lake Slack 봇 시작(HTTP 모드, port=%d)", config.port)
    app.start(port=config.port)


if __name__ == "__main__":
    main()
