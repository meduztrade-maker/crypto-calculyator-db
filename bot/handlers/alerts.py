from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import TradeStateError, cancel_alert, create_alert, list_active_alerts
from bot.database.models import User
from bot.keyboards.inline import AlertCB, NavCB, alert_item_keyboard, alerts_menu, cancel_button, home_button
from bot.services.price_feed import PriceLookupError, get_price
from bot.states.trade_states import AlertCreate
from bot.utils.formatting import InputError, dec_str, parse_decimal, safe_handler

router = Router(name="alerts")


def _normalize_symbol(raw: str) -> str:
    coin = raw.strip().upper().replace(" ", "")
    known_quotes = ("USDT", "USDC", "BUSD", "BTC", "ETH", "FDUSD", "TRY", "EUR")
    if not coin.endswith(known_quotes):
        coin += "USDT"
    return coin


def _alert_line(alert) -> str:
    arrow = "⬆️" if alert.direction.value == "ABOVE" else "⬇️"
    return f"{arrow} {alert.coin} → {dec_str(alert.target_price)} (qo'yilganda: {dec_str(alert.price_at_creation)})"


@router.callback_query(NavCB.filter(F.target == "alerts"))
@safe_handler
async def show_alerts(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    alerts = await list_active_alerts(session, user)
    if not alerts:
        await callback.message.edit_text("🔔 ALERT\n\nHozircha faol alert yo'q.", reply_markup=alerts_menu())
        await callback.answer()
        return

    await callback.message.edit_text("🔔 ALERT\n\nFaol alertlar:", reply_markup=alerts_menu())
    for alert in alerts:
        await callback.message.answer(_alert_line(alert), reply_markup=alert_item_keyboard(alert.id))
    await callback.answer()


@router.callback_query(NavCB.filter(F.target == "add_alert"))
@safe_handler
async def start_add_alert(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AlertCreate.coin)
    await callback.message.edit_text(
        "🪙 Coin nomini kiriting (masalan: BTCUSDT yoki BTC):", reply_markup=cancel_button()
    )
    await callback.answer()


@router.message(AlertCreate.coin)
@safe_handler
async def got_alert_coin(message: Message, state: FSMContext) -> None:
    coin = _normalize_symbol(message.text)
    if not coin or len(coin) > 32:
        raise InputError("❌ Noto'g'ri format.\n\nCoin nomini to'g'ri kiriting.\nMasalan: BTCUSDT")
    await state.update_data(coin=coin)
    await state.set_state(AlertCreate.price)
    await message.answer(f"💰 {coin} uchun alert narxini kiriting:", reply_markup=cancel_button())


@router.message(AlertCreate.price)
@safe_handler
async def got_alert_price(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    target = parse_decimal(message.text)
    data = await state.get_data()
    coin = data["coin"]

    try:
        current = await get_price(coin)
    except PriceLookupError as e:
        raise InputError(f"❌ {e}")

    alert = await create_alert(session, user, coin, target, current)
    await state.clear()

    arrow = "⬆️" if alert.direction.value == "ABOVE" else "⬇️"
    await message.answer(
        f"✅ Alert qo'yildi!\n\n{arrow} {alert.coin} → {dec_str(alert.target_price)}\n"
        f"Hozirgi narx: {dec_str(current)}\n\n"
        "Narx shu darajaga yetganda sizga xabar beraman.",
        reply_markup=home_button(),
    )


@router.callback_query(AlertCB.filter(F.action == "cancel"))
@safe_handler
async def cancel_alert_handler(callback: CallbackQuery, callback_data: AlertCB, session: AsyncSession, user: User) -> None:
    try:
        await cancel_alert(session, user, callback_data.alert_id)
    except TradeStateError:
        await callback.answer("❌ Bu alert allaqachon faol emas.", show_alert=True)
        return
    await callback.message.edit_text("❌ Alert bekor qilindi.")
    await callback.answer()
