from __future__ import annotations

import asyncio
import logging

import pytz
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.config import settings
from bot.handlers import (
    active,
    alerts,
    leverage,
    menu,
    pending,
    recent_trades,
    reports,
    settings as settings_handlers,
    start,
    trade_create,
)
from bot.middlewares.db import DbSessionMiddleware
from bot.services.alert_checker import check_and_notify_alerts
from bot.services.backup import run_backup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("meduz_bot")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()

    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    dp.include_router(start.router)
    # menu.router is second (after start, which only handles /start + the
    # inline "cancel" callback) but BEFORE every state-scoped flow router, so
    # a bottom-menu tap always wins over a stuck FSM state elsewhere.
    dp.include_router(menu.router)
    dp.include_router(trade_create.router)
    dp.include_router(pending.router)
    dp.include_router(active.router)
    dp.include_router(reports.router)
    dp.include_router(leverage.router)
    dp.include_router(recent_trades.router)
    dp.include_router(alerts.router)
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

    async def scheduled_alert_check() -> None:
        try:
            await check_and_notify_alerts(bot)
        except Exception:  # noqa: BLE001
            logger.exception("Alert check failed")

    scheduler.add_job(
        scheduled_alert_check,
        trigger="interval",
        seconds=30,
        id="alert_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    return scheduler


async def main() -> None:
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()

    if settings.webapp_url:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="MEDUZ App", web_app=WebAppInfo(url=settings.webapp_url))
            )
            logger.info("Chat menu button set to Mini App: %s", settings.webapp_url)
        except Exception:  # noqa: BLE001
            logger.exception("Could not set chat menu button (non-fatal)")

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
