"""Discord 봇 클라이언트 생성 및 실행 (telegram_bot/bot.py 와 대칭 패턴).

토큰 로드·검증은 main()/run() 호출 시점에만 일어난다 — 모듈 임포트 자체는 토큰 없이도 가능하다
(유닛 테스트·다른 모듈에서 import 할 때 환경변수 부재로 죽지 않게 하기 위함).
"""

import logging

import discord
from dotenv import load_dotenv

from core.storage import init_db
from discord_bot.config import load_config
from discord_bot.handlers import is_allowed, process_attachment

load_dotenv(".env.local")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_REPLY_LIMIT = 1900  # Discord 메시지 2000자 제한 여유 확보


def build_client(config) -> discord.Client:
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        logger.info("Discord 봇 로그인됨: %s", client.user)

    @client.event
    async def on_message(message: discord.Message):
        if message.author.bot:
            return
        if not is_allowed(message.channel.id, config.allowed_channel_ids):
            return
        if not message.attachments:
            return

        for attachment in message.attachments:
            file_size_mb = attachment.size / (1024 * 1024)
            if file_size_mb > config.max_file_size_mb:
                await message.channel.send(f"파일이 너무 큽니다(최대 {config.max_file_size_mb}MB).")
                continue

            try:
                file_bytes = await attachment.read()
                reply = await process_attachment(attachment.filename, file_bytes, lang=config.ocr_lang)
            except ValueError as exc:
                await message.channel.send(f"처리할 수 없습니다: {exc}")
                continue
            except Exception:
                logger.exception("Discord 첨부파일 처리 중 오류")
                await message.channel.send("처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
                continue

            if len(reply) > _REPLY_LIMIT:
                reply = reply[:_REPLY_LIMIT] + "\n…(이하 생략)"
            await message.channel.send(reply)

    return client


def main() -> None:
    init_db()
    config = load_config()
    client = build_client(config)
    logger.info("ocr-lake Discord 봇 시작")
    client.run(config.token)


if __name__ == "__main__":
    main()
