from __future__ import annotations

import functools
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from bot.database.models import Trade

logger = logging.getLogger("meduz_bot")


class InputError(Exception):
    """Raised for bad user input; the message is shown to the user as-is."""


def parse_decimal(raw: str, *, field_name: str = "qiymat", allow_negative: bool = False) -> Decimal:
    raw = raw.strip().replace(",", ".")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise InputError(
            f"❌ Noto'g'ri format.\n\nIltimos, faqat raqam kiriting.\nMasalan: 1.5"
        )
    if not allow_negative and value < 0:
        raise InputError("❌ Manfiy qiymat kiritib bo'lmaydi. Musbat raqam kiriting.")
    if value == 0:
        raise InputError("❌ Qiymat 0 bo'lishi mumkin emas.")
    return value


def parse_date(raw: str) -> datetime:
    raw = raw.strip()
    try:
        return datetime.strptime(raw, "%d.%m.%Y")
    except ValueError:
        raise InputError("❌ Noto'g'ri sana format.\n\nFormat: DD.MM.YYYY\nMasalan: 01.09.2026")


def dec_str(value: Decimal) -> str:
    """
    Plain decimal string with no trailing zeros and, crucially, no scientific
    notation. Decimal("500").normalize() alone yields Decimal("5E+2"), which
    would render as "5E+2" in an f-string — always route display through here
    instead of calling .normalize() directly in an f-string.
    """
    return format(value.normalize(), "f")


def fmt_rr(value: Decimal | None) -> str:
    if value is None:
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{dec_str(value)}R" if value != 0 else "0R"


def fmt_price(value: Decimal) -> str:
    return dec_str(value)


def trade_card_pending(trade: Trade) -> str:
    return (
        f"⏳ PENDING TRADE\n\n"
        f"{trade.coin}\n"
        f"{'🟢 LONG' if trade.direction.value == 'LONG' else '🔴 SHORT'}\n"
        f"Entry: {fmt_price(trade.entry_price)}\n"
        f"SL: {fmt_price(trade.stop_loss_price)}\n"
        f"Risk: {dec_str(trade.risk_percent)}%\n"
        f"SL masofa: {dec_str(trade.stop_distance_percent)}%"
    )


def trade_card_active(trade: Trade) -> str:
    return (
        f"🟢 ACTIVE\n\n"
        f"{trade.coin}\n"
        f"{'🟢 LONG' if trade.direction.value == 'LONG' else '🔴 SHORT'}\n"
        f"Entry: {fmt_price(trade.entry_price)}\n"
        f"SL: {fmt_price(trade.stop_loss_price)}\n"
        f"Risk: {dec_str(trade.risk_percent)}%"
    )


def trade_card_missed(trade: Trade) -> str:
    return f"⚪ {trade.coin}\n{trade.direction.value}\nStatus: MISSED\nEntry'ga kelmadi"


def trade_card_closed(trade: Trade) -> str:
    result_label = {
        "SL": "🛑 SL",
        "BU": "🟡 B/U",
        "TP": "🟢 TP",
    }.get(trade.result_type.value if trade.result_type else "", "-")
    return (
        f"✅ CLOSED\n\n"
        f"{trade.coin}\n"
        f"{'🟢 LONG' if trade.direction.value == 'LONG' else '🔴 SHORT'}\n"
        f"Natija: {result_label}\n"
        f"RR: {fmt_rr(trade.result_rr)}"
    )


def trade_card_generic(trade: Trade) -> str:
    """Status-aware one-trade summary — used by the 'oxirgi tradelar' (recent trades) screen."""
    status_label = {
        "PENDING": "⏳ PENDING",
        "ACTIVE": "🟢 ACTIVE",
        "CLOSED": "✅ CLOSED",
        "MISSED": "⚪ MISSED",
        "CANCELLED": "⚪ CANCELLED",
    }.get(trade.status.value, trade.status.value)

    lines = [
        status_label,
        "",
        trade.coin,
        "🟢 LONG" if trade.direction.value == "LONG" else "🔴 SHORT",
        f"Entry: {fmt_price(trade.entry_price)}",
        f"SL: {fmt_price(trade.stop_loss_price)}",
    ]
    if trade.status.value == "CLOSED":
        result_label = {"SL": "🛑 SL", "BU": "🟡 B/U", "TP": "🟢 TP"}.get(
            trade.result_type.value if trade.result_type else "", "-"
        )
        lines.append(f"Natija: {result_label} ({fmt_rr(trade.result_rr)})")
    lines.append(f"Sana: {trade.created_at.strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(lines)


def safe_handler(func):
    """
    Decorator: never let a handler crash the bot (spec section 27).
    Catches InputError and shows its message; logs and reports anything else generically.
    """

    @functools.wraps(func)
    async def wrapper(event, *args, **kwargs):
        try:
            return await func(event, *args, **kwargs)
        except InputError as e:
            reply = getattr(event, "message", event)
            await reply.answer(str(e)) if hasattr(reply, "answer") else None
        except Exception:  # noqa: BLE001
            logger.exception("Unhandled error in handler %s", func.__name__)
            reply = getattr(event, "message", event)
            try:
                await reply.answer("❌ Kutilmagan xatolik yuz berdi. Iltimos qayta urinib ko'ring.")
            except Exception:  # noqa: BLE001
                logger.exception("Failed to notify user of error")

    return wrapper
