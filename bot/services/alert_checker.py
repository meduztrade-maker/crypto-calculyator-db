from __future__ import annotations

import logging

from aiogram import Bot

from bot.database.crud import list_all_active_alerts, mark_alert_triggered
from bot.database.engine import async_session_maker
from bot.database.models import AlertDirection, User
from bot.services.price_feed import get_all_prices, get_price_safe
from bot.utils.formatting import dec_str

logger = logging.getLogger("meduz_bot")


async def check_and_notify_alerts(bot: Bot) -> None:
    async with async_session_maker() as session:
        alerts = await list_all_active_alerts(session)
        if not alerts:
            return

        prices = await get_all_prices()

        # Binance spot doesn't list everything (e.g. futures-only launches
        # like VVV) - fill in just the coins actually missing, one lookup
        # each via the Binance futures/Bybit/MEXC fallback chain, instead
        # of silently skipping that alert forever.
        missing_coins = {a.coin for a in alerts if a.coin not in prices}
        for coin in missing_coins:
            price = await get_price_safe(coin)
            if price is not None:
                prices[coin] = price

        if not prices:
            return

        for alert in alerts:
            current = prices.get(alert.coin)
            if current is None:
                continue

            hit = (
                (alert.direction == AlertDirection.ABOVE and current >= alert.target_price)
                or (alert.direction == AlertDirection.BELOW and current <= alert.target_price)
            )
            if not hit:
                continue

            updated = await mark_alert_triggered(session, alert.id)
            if updated is None:
                continue  # already handled by a concurrent tick

            user = await session.get(User, alert.user_id)
            if user is None:
                continue

            arrow = "⬆️" if alert.direction == AlertDirection.ABOVE else "⬇️"
            try:
                await bot.send_message(
                    user.telegram_id,
                    f"🔔 ALERT!\n\n{arrow} {alert.coin} narxi {dec_str(alert.target_price)} ga yetdi!\n\n"
                    f"Hozirgi narx: {dec_str(current)}",
                )
            except Exception:  # noqa: BLE001
                logger.exception("Could not deliver alert notification to user %s", user.telegram_id)
