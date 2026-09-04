from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ---------------------------------------------------------------------------
# Persistent bottom menu (ReplyKeyboardMarkup) — this is the *only* way the
# top-level sections are reached. It always sits above the text input, so it
# can never get "lost" in the chat scroll the way inline buttons on an old
# message can. Section screens themselves still use inline keyboards for
# in-context actions (pick a trade, close it, cancel an alert, ...).
# ---------------------------------------------------------------------------

MENU_ADD_TRADE = "➕ Trade qo'shish"
MENU_PENDING = "⏳ Pending"
MENU_ACTIVE = "🟢 Active"
MENU_REPORTS = "📊 Hisobot"
MENU_LEVERAGE = "🧮 Leverage"
MENU_RECENT = "🗑 Oxirgi tradelar"
MENU_ALERTS = "🔔 Alert"
MENU_SETTINGS = "⚙️ Sozlamalar"

MENU_LABELS = [
    MENU_ADD_TRADE, MENU_PENDING, MENU_ACTIVE, MENU_REPORTS,
    MENU_LEVERAGE, MENU_RECENT, MENU_ALERTS, MENU_SETTINGS,
]


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    for label in MENU_LABELS:
        b.button(text=label)
    b.adjust(2, 2, 2, 2)
    return b.as_markup(resize_keyboard=True)


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
    target: str  # pending | active | reports | leverage | settings | add_trade | recent_trades | alerts | add_alert | change_margin | cancel


class BackupCB(CallbackData, prefix="backup"):
    action: str  # now | restore | last | restore_yes | restore_no


class TradeListItemCB(CallbackData, prefix="tli"):
    list_type: str  # pending | active | recent
    trade_id: int


class RecentTradeCB(CallbackData, prefix="rtrade"):
    action: str  # delete | confirm_delete
    trade_id: int


class AlertCB(CallbackData, prefix="alert"):
    action: str  # view | cancel
    alert_id: int


# ---------------------------------------------------------------------------
# Generic nav helpers
# ---------------------------------------------------------------------------

def cancel_button() -> InlineKeyboardMarkup:
    """Single inline button shown during a multi-step text prompt (coin, price, etc.)."""
    b = InlineKeyboardBuilder()
    b.button(text="❌ Bekor qilish", callback_data=NavCB(target="cancel"))
    return b.as_markup()


def back_button(target: str, label: str = "🔙 Orqaga") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=label, callback_data=NavCB(target=target))
    return b.as_markup()


def direction_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🟢 LONG", callback_data=DirectionCB(value="LONG"))
    b.button(text="🔴 SHORT", callback_data=DirectionCB(value="SHORT"))
    b.button(text="❌ Bekor qilish", callback_data=NavCB(target="cancel"))
    b.adjust(2, 1)
    return b.as_markup()


RISK_PRESETS = ["0.5", "1", "1.5", "2", "2.5", "3"]


def risk_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for r in RISK_PRESETS:
        b.button(text=f"{r}%", callback_data=RiskCB(value=r))
    b.button(text="✏️ Custom", callback_data=RiskCB(value="custom"))
    b.button(text="❌ Bekor qilish", callback_data=NavCB(target="cancel"))
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
    b.button(text="🔙 Orqaga", callback_data=NavCB(target="active"))
    b.adjust(3)
    return b.as_markup()


# ---------------------------------------------------------------------------
# Pending — list + detail
# ---------------------------------------------------------------------------

def pending_list_keyboard(trades) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in trades:
        label = f"⏳ {t.coin} {t.direction.value}"
        b.button(text=label, callback_data=TradeListItemCB(list_type="pending", trade_id=t.id))
    b.adjust(1)
    return b.as_markup()


def pending_detail_keyboard(trade_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🟢 Activate", callback_data=TradeCB(action="activate", trade_id=trade_id))
    b.button(text="⚪ Missed / Cancel", callback_data=TradeCB(action="miss", trade_id=trade_id))
    b.button(text="🗑 Delete", callback_data=TradeCB(action="delete", trade_id=trade_id))
    b.button(text="🔙 Orqaga", callback_data=NavCB(target="pending"))
    b.adjust(1)
    return b.as_markup()


# ---------------------------------------------------------------------------
# Active — list + detail
# ---------------------------------------------------------------------------

def active_list_keyboard(trades) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in trades:
        label = f"🟢 {t.coin} {t.direction.value}"
        b.button(text=label, callback_data=TradeListItemCB(list_type="active", trade_id=t.id))
    b.adjust(1)
    return b.as_markup()


def active_detail_keyboard(trade_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛑 SL", callback_data=TradeCB(action="sl", trade_id=trade_id))
    b.button(text="🟡 B/U", callback_data=TradeCB(action="bu", trade_id=trade_id))
    b.button(text="🟢 TP", callback_data=TradeCB(action="tp", trade_id=trade_id))
    b.button(text="🔙 Orqaga", callback_data=NavCB(target="active"))
    b.adjust(3, 1)
    return b.as_markup()


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def reports_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📅 Kunlik", callback_data=ReportCB(period="daily"))
    b.button(text="📆 Haftalik", callback_data=ReportCB(period="weekly"))
    b.button(text="🗓 Davr tanlash", callback_data=ReportCB(period="custom"))
    b.adjust(1)
    return b.as_markup()


# ---------------------------------------------------------------------------
# Settings / backup
# ---------------------------------------------------------------------------

def settings_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💵 Change Margin", callback_data=NavCB(target="change_margin"))
    b.button(text="☁️ Backup Now", callback_data=BackupCB(action="now"))
    b.button(text="🔄 Restore", callback_data=BackupCB(action="restore"))
    b.button(text="🕐 Last Backup", callback_data=BackupCB(action="last"))
    b.adjust(1)
    return b.as_markup()


def restore_confirm_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Yes, Restore", callback_data=BackupCB(action="restore_yes"))
    b.button(text="❌ Cancel", callback_data=BackupCB(action="restore_no"))
    b.adjust(2)
    return b.as_markup()


# ---------------------------------------------------------------------------
# Recent trades — list + detail
# ---------------------------------------------------------------------------

def recent_list_keyboard(trades) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    status_icon = {"PENDING": "⏳", "ACTIVE": "🟢", "CLOSED": "✅", "MISSED": "⚪", "CANCELLED": "⚪"}
    for t in trades:
        icon = status_icon.get(t.status.value, "•")
        b.button(text=f"{icon} {t.coin} {t.direction.value}", callback_data=TradeListItemCB(list_type="recent", trade_id=t.id))
    b.adjust(1)
    return b.as_markup()


def recent_trade_detail_keyboard(trade_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🗑 O'chirish", callback_data=RecentTradeCB(action="delete", trade_id=trade_id))
    b.button(text="🔙 Orqaga", callback_data=NavCB(target="recent_trades"))
    b.adjust(1)
    return b.as_markup()


def recent_trade_confirm_keyboard(trade_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, o'chirish", callback_data=RecentTradeCB(action="confirm_delete", trade_id=trade_id))
    b.button(text="❌ Bekor qilish", callback_data=NavCB(target="recent_trades"))
    b.adjust(1)
    return b.as_markup()


# ---------------------------------------------------------------------------
# Alerts — list + detail
# ---------------------------------------------------------------------------

def alerts_menu(alerts) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for a in alerts:
        arrow = "⬆️" if a.direction.value == "ABOVE" else "⬇️"
        b.button(text=f"{arrow} {a.coin} → {a.target_price.normalize()}", callback_data=AlertCB(action="view", alert_id=a.id))
    b.button(text="➕ Yangi alert", callback_data=NavCB(target="add_alert"))
    b.adjust(1)
    return b.as_markup()


def alert_detail_keyboard(alert_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Bekor qilish", callback_data=AlertCB(action="cancel", alert_id=alert_id))
    b.button(text="🔙 Orqaga", callback_data=NavCB(target="alerts"))
    b.adjust(1)
    return b.as_markup()
