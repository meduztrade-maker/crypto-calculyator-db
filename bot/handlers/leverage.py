from __future__ import annotations

from decimal import Decimal

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import list_margin_presets
from bot.database.models import User
from bot.keyboards.inline import cancel_button
from bot.services.leverage_calc import calculate_leverage_for_accounts, format_leverage_results_multi
from bot.states.trade_states import LeverageCalc
from bot.utils.formatting import parse_decimal, safe_handler

router = Router(name="leverage")


async def render_leverage(message: Message, state: FSMContext) -> None:
    await state.set_state(LeverageCalc.distance)
    await message.answer("Entry'dan Stop Lossgacha necha %?", reply_markup=cancel_button())


@router.message(LeverageCalc.distance)
@safe_handler
async def got_distance(message: Message, state: FSMContext, user: User, session: AsyncSession) -> None:
    distance = parse_decimal(message.text)

    presets = await list_margin_presets(session, user)
    accounts = [(p.label, p.amount) for p in presets] if presets else [("Margin", user.margin)]

    await state.update_data(
        distance=str(distance),
        accounts=[(label, str(margin)) for label, margin in accounts],
        risks=[],
        idx=0,
    )
    await state.set_state(LeverageCalc.risk_amount)
    label, margin = accounts[0]
    await message.answer(
        f"{label} (${margin}) uchun necha dollar risk qilmoqchisiz?", reply_markup=cancel_button()
    )


@router.message(LeverageCalc.risk_amount)
@safe_handler
async def got_risk_amount(message: Message, state: FSMContext) -> None:
    """Loops once per saved margin preset, asking that account's OWN risk
    $ - a $50 account and a $500 account should never share one risk
    figure, since the same dollar amount is a very different percentage
    of each. Once every account has an answer, shows all leverages at
    once."""
    risk = parse_decimal(message.text)
    data = await state.get_data()
    accounts: list[tuple[str, str]] = data["accounts"]
    risks: list[str] = data["risks"] + [str(risk)]
    idx: int = data["idx"] + 1

    if idx < len(accounts):
        await state.update_data(risks=risks, idx=idx)
        label, margin = accounts[idx]
        await message.answer(
            f"{label} (${margin}) uchun necha dollar risk qilmoqchisiz?", reply_markup=cancel_button()
        )
        return

    distance = Decimal(data["distance"])
    triples = [(accounts[i][0], Decimal(accounts[i][1]), Decimal(risks[i])) for i in range(len(accounts))]
    await state.clear()

    results = calculate_leverage_for_accounts(triples, distance)
    await message.answer(format_leverage_results_multi(distance, results))
