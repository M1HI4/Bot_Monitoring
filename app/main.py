from __future__ import annotations

import asyncio
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from app.bot.dispatcher import build_dispatcher
from app.container import build_services
from app.utils.logging import configure_logging


async def run() -> None:
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")
    configure_logging("INFO")

    services = build_services(project_root)
    services.config.ensure_runtime_files()
    runtime_config = services.config.load_runtime_config()
    configure_logging(runtime_config.app.log_level)

    bot = Bot(
        token=runtime_config.telegram.token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dispatcher = build_dispatcher(services)
    alert_task = services.alerting.start(bot)
    try:
        await dispatcher.start_polling(bot, services=services)
    finally:
        if alert_task:
            await services.alerting.stop()
        await services.prometheus.close()
        await bot.session.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
