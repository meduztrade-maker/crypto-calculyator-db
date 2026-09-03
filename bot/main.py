from __future__ import annotations

import asyncio
import logging

import pytz
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import settings
from bot.handlers import active, leverage, pending, reports, settings as settings_handlers, start, trade_create
from bot.middlewares.db import DbSessionMiddleware
from bot.services.backup import run_backup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("meduz_bot")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    dp.include_router(start.router)
    dp.include_router(trade_create.router)
    dp.include_router(pending.router)
    dp.include_router(active.router)
    dp.include_router(reports.router)
    dp.include_router(leverage.router)
    dp.include_router(settings_handlers.router)

    return dp


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    tz = pytz.timezone(settings.timezone)
    scheduler = AsyncIOScheduler(timezone=tz)

    async def scheduled_backup() -> None:
        logger.info("Running scheduled daily backup")
        try:
            await run_backup(bot, manual=False)
        except Exception:  # noqa: BLE001
            logger.exception("Scheduled backup failed")

    scheduler.add_job(
        scheduled_backup,
        trigger="cron",
        hour=settings.backup_hour_local,
        minute=0,
        id="daily_backup",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


async def main() -> None:
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()

    scheduler = setup_scheduler(bot)

    try:
        logger.info("MEDUZ TRADING JOURNAL bot starting (polling mode)...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
