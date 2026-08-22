"""텔레그램 봇 Application 생성 및 실행(polling)"""

import logging

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

load_dotenv(".env.local")

from telegram_bot.config import load_config
from telegram_bot.handlers.ocr_handlers import handle_photo, start, structure
from telegram_bot.handlers.pdf_video_handlers import handle_pdf, handle_video
from telegram_bot.handlers.office_handlers import handle_hwp, handle_pptx
from core.storage import init_db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_application() -> Application:
    init_db()
    config = load_config()
    application = Application.builder().token(config.token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("structure", structure))
    application.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo)
    )
    application.add_handler(
        MessageHandler(filters.Document.PDF, handle_pdf)
    )
    application.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video)
    )
    application.add_handler(
        MessageHandler(filters.Document.FileExtension("pptx"), handle_pptx)
    )
    application.add_handler(
        MessageHandler(filters.Document.FileExtension("hwp"), handle_hwp)
    )

    return application


def main() -> None:
    application = build_application()
    logger.info("ocr-lake 텔레그램 봇 시작(polling)")
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
