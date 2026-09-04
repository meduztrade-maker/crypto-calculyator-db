from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import (
    TradeStateError,
    close_trade_sl,
    close_trade_with_rr,
    get_user_trade,
    list_active_trades,
)
from bot.database.models import ResultType, User
from bot.keyboards.inline import (
    NavCB,
    RRCB,
    TradeCB,
    TradeListItemCB,
    active_detail_keyboard,
    active_list_keyboard,
    back_button,
    cancel_button,
    rr_keyboard,
)
from bot.states.trade_states import TradeClose
from bot.utils.formatting import InputError, dec_str, parse_decimal, safe_handler, trade_card_active, trade_card_closed

router = Router(name="active")


async def _active_list_content(session: AsyncSession, user: User):
    trades = await list_active_trades(session, user)
    if not trades:
        return "🟢 Active trade'lar yo'q.", None
    text = f"🟢 ACTIVE ({len(trades)} ta)\n\nBatafsil ko'rish uchun tanlang:"
    return text, active_list_keyboard(trades)


async def render_active(message: Message, session: AsyncSession, user: User) -> None:
    text, kb = await _active_list_content(session, user)
    await message.answer(text, reply_markup=kb)


@router.callback_query(NavCB.filter(F.target == "active"))
@safe_handler
async def back_to_active(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    text, kb = await _active_list_content(session, user)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(TradeListItemCB.filter(F.list_type == "active"))
@safe_handler
async def active_detail(callback: CallbackQuery, callback_data: TradeListItemCB, session: AsyncSession, user: User) -> None:
    trade = await get_user_trade(session, user, callback_data.trade_id)
    if trade is None or trade.status.value != "ACTIVE":
        await callback.answer("❌ Bu trade endi active emas.", show_alert=True)
        text, kb = await _active_list_content(session, user)
        await callback.message.edit_text(text, reply_markup=kb)
        return
    await callback.message.edit_text(trade_card_active(trade), reply_markup=active_detail_keyboard(trade.id))
    await callback.answer()


@router.callback_query(TradeCB.filter(F.action == "sl"))
@safe_handler
async def close_sl_prompt(callback: CallbackQuery, callback_data: TradeCB, state: FSMContext, session: AsyncSession, user: User) -> None:
    trade = await get_user_trade(session, user, callback_data.trade_id)
    if trade is None or trade.status.value != "ACTIVE":
        await callback.answer("❌ Bu trade aktiv emas.", show_alert=True)
        return

    await state.set_state(TradeClose.screenshot)
    await state.update_data(trade_id=trade.id, result_type="SL", rr="-1")
    await callback.message.edit_text(
        f"🛑 Trade SL bo'ldimi?\n\nRisk: {dec_str(trade.risk_percent)}%\n\nNatija: -1R"
    )
    await callback.message.answer("📸 Trade yopilgandan keyingi screenshotni yuboring.", reply_markup=cancel_button())
    await callback.answer()


@router.callback_query(TradeCB.filter(F.action.in_({"bu", "tp"})))
@safe_handler
async def close_rr_prompt(callback: CallbackQuery, callback_data: TradeCB, session: AsyncSession, user: User) -> None:
    trade = await get_user_trade(session, user, callback_data.trade_id)
    if trade is None or trade.status.value != "ACTIVE":
        await callback.answer("❌ Bu trade aktiv emas.", show_alert=True)
        return

    kind = callback_data.action
    label = "🟡 B/U" if kind == "bu" else "🟢 TP"
    await callback.message.edit_text(
        f"{label} necha RR'da yopildi?", reply_markup=rr_keyboard(kind, trade.id)
    )
    await callback.answer()


@router.callback_query(RRCB.filter())
@safe_handler
async def rr_selected(callback: CallbackQuery, callback_data: RRCB, state: FSMContext, session: AsyncSession, user: User) -> None:
    trade = await get_user_trade(session, user, callback_data.trade_id)
    if trade is None or trade.status.value != "ACTIVE":
        await callback.answer("❌ Bu trade aktiv emas.", show_alert=True)
        return

    result_type = "BU" if callback_data.kind == "bu" else "TP"

    if callback_data.value == "custom":
        await state.set_state(TradeClose.rr_custom)
        await state.update_data(trade_id=trade.id, result_type=result_type)
        await callback.message.edit_text("✏️ RR qiymatini kiriting (masalan: 1.8):", reply_markup=cancel_button())
        await callback.answer()
        return

    rr = callback_data.value
    label = "🟡 B/U" if result_type == "BU" else "🟢 TP"
    await state.set_state(TradeClose.screenshot)
    await state.update_data(trade_id=trade.id, result_type=result_type, rr=rr)
    await callback.message.edit_text(f"{label} +{rr}R")
    await callback.message.answer("📸 Trade yopilgandan keyingi screenshotni yuboring.", reply_markup=cancel_button())
    await callback.answer()


@router.message(TradeClose.rr_custom)
@safe_handler
async def rr_custom_entered(message: Message, state: FSMContext) -> None:
    value = parse_decimal(message.text, allow_negative=True)
    data = await state.get_data()
    result_type = data["result_type"]
    label = "🟡 B/U" if result_type == "BU" else "🟢 TP"
    sign = "+" if value >= 0 else ""
    await state.set_state(TradeClose.screenshot)
    await state.update_data(rr=str(value))
    await message.answer(f"{label} {sign}{dec_str(value)}R")
    await message.answer("📸 Trade yopilgandan keyingi screenshotni yuboring.", reply_markup=cancel_button())


@router.message(TradeClose.screenshot, F.photo)
@safe_handler
async def close_screenshot_received(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    file_id = message.photo[-1].file_id
    trade_id = data["trade_id"]
    result_type = data["result_type"]
    rr = Decimal(data["rr"])

    try:
        if result_type == "SL":
            trade = await close_trade_sl(session, user, trade_id, file_id)
        else:
            trade = await close_trade_with_rr(session, user, trade_id, ResultType(result_type), rr, file_id)
    except TradeStateError:
        await state.clear()
        await message.answer("❌ Bu trade allaqachon yopilgan yoki topilmadi.")
        return

    await state.clear()
    await message.answer(trade_card_closed(trade), reply_markup=back_button("active", "🔙 Active ro'yxatiga"))


@router.message(TradeClose.screenshot)
@safe_handler
async def close_screenshot_wrong_type(message: Message) -> None:
    raise InputError("❌ Iltimos, rasm (screenshot) yuboring, matn emas.")
