from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ---------------------------------------------------------------------------
# Callback data factories (typed, avoids fragile string-splitting)
# ---------------------------------------------------------------------------

class TradeCB(CallbackData, prefix="trade"):
    action: str  # activate | miss | delete | sl | bu | tp
    trade_id: int


class RRCB(CallbackData, prefix="rr"):
    kind: str  # bu | tp
    trade_id: int
    value: str  # decimal-as-string, or "custom"


class RiskCB(CallbackData, prefix="risk"):
    value: str  # decimal-as-string, or "custom"


class DirectionCB(CallbackData, prefix="dir"):
    value: str  # LONG | SHORT


class ReportCB(CallbackData, prefix="report"):
    period: str  # daily | weekly | custom


class NavCB(CallbackData, prefix="nav"):
    target: str  # home | pending | active | reports | leverage | settings | add_trade


class BackupCB(CallbackData, prefix="backup"):
    action: str  # now | restore | last | restore_yes | restore_no


class RecentTradeCB(CallbackData, prefix="rtrade"):
    action: str  # delete | confirm_delete
    trade_id: int


class AlertCB(CallbackData, prefix="alert"):
    action: str  # cancel
    alert_id: int


# ---------------------------------------------------------------------------
# Static keyboards
# ---------------------------------------------------------------------------

def main_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Trade qo'shish", callback_data=NavCB(target="add_trade"))
    b.button(text="⏳ Pending", callback_data=NavCB(target="pending"))
    b.button(text="🟢 Active", callback_data=NavCB(target="active"))
    b.button(text="📊 Hisobot ulashish", callback_data=NavCB(target="reports"))
    b.button(text="🧮 Leverage Calculator", callback_data=NavCB(target="leverage"))
    b.button(text="🗑 Oxirgi tradelar", callback_data=NavCB(target="recent_trades"))
    b.button(text="🔔 Alert", callback_data=NavCB(target="alerts"))
    b.button(text="⚙️ Sozlamalar", callback_data=NavCB(target="settings"))
    b.adjust(1)
    return b.as_markup()


def home_button() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏠 Bosh menu", callback_data=NavCB(target="home"))
    return b.as_markup()


def cancel_button() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Bekor qilish", callback_data=NavCB(target="home"))
    return b.as_markup()


def direction_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🟢 LONG", callback_data=DirectionCB(value="LONG"))
    b.button(text="🔴 SHORT", callback_data=DirectionCB(value="SHORT"))
    b.button(text="❌ Bekor qilish", callback_data=NavCB(target="home"))
    b.adjust(2, 1)
    return b.as_markup()


RISK_PRESETS = ["0.5", "1", "1.5", "2", "2.5", "3"]


def risk_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for r in RISK_PRESETS:
        b.button(text=f"{r}%", callback_data=RiskCB(value=r))
    b.button(text="✏️ Custom", callback_data=RiskCB(value="custom"))
    b.button(text="❌ Bekor qilish", callback_data=NavCB(target="home"))
    b.adjust(3, 3, 1, 1)
    return b.as_markup()


BU_RR_PRESETS = ["0.5", "0.75", "1", "1.5", "2", "2.5", "3", "4", "5"]
TP_RR_PRESETS = ["1", "1.5", "2", "2.5", "3", "4", "5", "6", "8", "10"]


def rr_keyboard(kind: str, trade_id: int) -> InlineKeyboardMarkup:
    presets = BU_RR_PRESETS if kind == "bu" else TP_RR_PRESETS
    b = InlineKeyboardBuilder()
    for r in presets:
        b.button(text=f"{r}R", callback_data=RRCB(kind=kind, trade_id=trade_id, value=r))
    b.button(text="✏️ Custom RR", callback_data=RRCB(kind=kind, trade_id=trade_id, value="custom"))
    b.adjust(3)
    return b.as_markup()


def pending_trade_keyboard(trade_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🟢 Activate", callback_data=TradeCB(action="activate", trade_id=trade_id))
    b.button(text="⚪ Missed / Cancel", callback_data=TradeCB(action="miss", trade_id=trade_id))
    b.button(text="🗑 Delete", callback_data=TradeCB(action="delete", trade_id=trade_id))
    b.button(text="🏠 Bosh menu", callback_data=NavCB(target="home"))
    b.adjust(1)
    return b.as_markup()


def active_trade_keyboard(trade_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛑 SL", callback_data=TradeCB(action="sl", trade_id=trade_id))
    b.button(text="🟡 B/U", callback_data=TradeCB(action="bu", trade_id=trade_id))
    b.button(text="🟢 TP", callback_data=TradeCB(action="tp", trade_id=trade_id))
    b.button(text="🏠 Bosh menu", callback_data=NavCB(target="home"))
    b.adjust(3, 1)
    return b.as_markup()


def reports_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📅 Kunlik", callback_data=ReportCB(period="daily"))
    b.button(text="📆 Haftalik", callback_data=ReportCB(period="weekly"))
    b.button(text="🗓 Davr tanlash", callback_data=ReportCB(period="custom"))
    b.button(text="🏠 Bosh menu", callback_data=NavCB(target="home"))
    b.adjust(1)
    return b.as_markup()


def settings_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💵 Change Margin", callback_data=NavCB(target="change_margin"))
    b.button(text="☁️ Backup Now", callback_data=BackupCB(action="now"))
    b.button(text="🔄 Restore", callback_data=BackupCB(action="restore"))
    b.button(text="🕐 Last Backup", callback_data=BackupCB(action="last"))
    b.button(text="🏠 Bosh menu", callback_data=NavCB(target="home"))
    b.adjust(1)
    return b.as_markup()


def restore_confirm_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Yes, Restore", callback_data=BackupCB(action="restore_yes"))
    b.button(text="❌ Cancel", callback_data=BackupCB(action="restore_no"))
    b.adjust(2)
    return b.as_markup()


def recent_trade_keyboard(trade_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🗑 O'chirish", callback_data=RecentTradeCB(action="delete", trade_id=trade_id))
    b.adjust(1)
    return b.as_markup()


def recent_trade_confirm_keyboard(trade_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, o'chirish", callback_data=RecentTradeCB(action="confirm_delete", trade_id=trade_id))
    b.button(text="❌ Bekor qilish", callback_data=NavCB(target="recent_trades"))
    b.adjust(1)
    return b.as_markup()


def alerts_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="➕ Yangi alert", callback_data=NavCB(target="add_alert"))
    b.button(text="🏠 Bosh menu", callback_data=NavCB(target="home"))
    b.adjust(1)
    return b.as_markup()


def alert_item_keyboard(alert_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Bekor qilish", callback_data=AlertCB(action="cancel", alert_id=alert_id))
    b.adjust(1)
    return b.as_markup()
