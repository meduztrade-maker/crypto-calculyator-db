from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import create_pending_trade
from bot.database.models import Direction, User
from bot.keyboards.inline import (
    DirectionCB,
    NavCB,
    RiskCB,
    back_button,
    cancel_button,
    direction_keyboard,
    risk_keyboard,
)
from bot.states.trade_states import TradeCreate
from bot.utils.formatting import InputError, parse_decimal, safe_handler, trade_card_pending

router = Router(name="trade_create")


async def render_add_trade(message: Message, state: FSMContext) -> None:
    await state.set_state(TradeCreate.coin)
    await message.answer("🪙 Coin nomini kiriting:", reply_markup=cancel_button())


@router.message(TradeCreate.coin)
@safe_handler
async def got_coin(message: Message, state: FSMContext) -> None:
    coin = message.text.strip().upper()
    if not coin or len(coin) > 32:
        raise InputError("❌ Noto'g'ri format.\n\nCoin nomini to'g'ri kiriting.\nMasalan: BTCUSDT")
    await state.update_data(coin=coin)
    await state.set_state(TradeCreate.direction)
    await message.answer("📈 Trade yo'nalishini tanlang:", reply_markup=direction_keyboard())


@router.callback_query(TradeCreate.direction, DirectionCB.filter())
@safe_handler
async def got_direction(callback: CallbackQuery, callback_data: DirectionCB, state: FSMContext) -> None:
    await state.update_data(direction=callback_data.value)
    await state.set_state(TradeCreate.risk)
    await callback.message.edit_text("⚠️ Ushbu trade uchun qancha risk qilasiz?", reply_markup=risk_keyboard())
    await callback.answer()


@router.callback_query(TradeCreate.risk, RiskCB.filter())
@safe_handler
async def got_risk(callback: CallbackQuery, callback_data: RiskCB, state: FSMContext) -> None:
    if callback_data.value == "custom":
        await state.set_state(TradeCreate.risk_custom)
        await callback.message.edit_text("✏️ Risk foizini kiriting (masalan: 1.25):", reply_markup=cancel_button())
        await callback.answer()
        return

    await state.update_data(risk_percent=callback_data.value)
    await state.set_state(TradeCreate.entry)
    await callback.message.edit_text("🎯 Entry narxini kiriting:", reply_markup=cancel_button())
    await callback.answer()


@router.message(TradeCreate.risk_custom)
@safe_handler
async def got_custom_risk(message: Message, state: FSMContext) -> None:
    value = parse_decimal(message.text)
    await state.update_data(risk_percent=str(value))
    await state.set_state(TradeCreate.entry)
    await message.answer("🎯 Entry narxini kiriting:", reply_markup=cancel_button())


@router.message(TradeCreate.entry)
@safe_handler
async def got_entry(message: Message, state: FSMContext) -> None:
    value = parse_decimal(message.text)
    await state.update_data(entry_price=str(value))
    await state.set_state(TradeCreate.stop_loss)
    await message.answer("🛑 Stop Loss narxini kiriting:", reply_markup=cancel_button())


@router.message(TradeCreate.stop_loss)
@safe_handler
async def got_stop_loss(message: Message, state: FSMContext) -> None:
    value = parse_decimal(message.text)
    await state.update_data(stop_loss_price=str(value))
    await state.set_state(TradeCreate.screenshot)
    await message.answer("📸 Trade screenshotini yuboring.", reply_markup=cancel_button())


@router.message(TradeCreate.screenshot, F.photo)
@safe_handler
async def got_screenshot(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    data = await state.get_data()
    file_id = message.photo[-1].file_id

    trade = await create_pending_trade(
        session=session,
        user=user,
        coin=data["coin"],
        direction=Direction(data["direction"]),
        risk_percent=Decimal(data["risk_percent"]),
        entry_price=Decimal(data["entry_price"]),
        stop_loss_price=Decimal(data["stop_loss_price"]),
        opening_screenshot_file_id=file_id,
    )
    await state.clear()
    await message.answer(trade_card_pending(trade), reply_markup=back_button("pending", "🔙 Pending ro'yxatiga"))


@router.message(TradeCreate.screenshot)
@safe_handler
async def screenshot_wrong_type(message: Message) -> None:
    raise InputError("❌ Iltimos, rasm (screenshot) yuboring, matn emas.")
