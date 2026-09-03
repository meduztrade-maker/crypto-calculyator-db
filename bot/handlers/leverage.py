from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database.models import User
from bot.keyboards.inline import NavCB, cancel_button, home_button
from bot.services.leverage_calc import calculate_leverage, format_leverage_result
from bot.states.trade_states import LeverageCalc
from bot.utils.formatting import parse_decimal, safe_handler

router = Router(name="leverage")


@router.callback_query(NavCB.filter(F.target == "leverage"))
@safe_handler
async def start_leverage(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(LeverageCalc.distance)
    await callback.message.edit_text("Entry'dan Stop Lossgacha necha %?", reply_markup=cancel_button())
    await callback.answer()


@router.message(LeverageCalc.distance)
@safe_handler
async def got_distance(message: Message, state: FSMContext) -> None:
    value = parse_decimal(message.text)
    await state.update_data(distance=str(value))
    await state.set_state(LeverageCalc.risk_amount)
    await message.answer("Qancha dollar risk qilmoqchisiz?", reply_markup=cancel_button())


@router.message(LeverageCalc.risk_amount)
@safe_handler
async def got_risk_amount(message: Message, state: FSMContext, user: User) -> None:
    from decimal import Decimal

    risk = parse_decimal(message.text)
    data = await state.get_data()
    distance = Decimal(data["distance"])
    await state.clear()

    result = calculate_leverage(margin=user.margin, risk=risk, sl_distance_percent=distance)
    await message.answer(format_leverage_result(result), reply_markup=home_button())
