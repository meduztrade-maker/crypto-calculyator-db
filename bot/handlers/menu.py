from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.handlers.active import render_active
from bot.handlers.alerts import render_alerts
from bot.handlers.leverage import render_leverage
from bot.handlers.pending import render_pending
from bot.handlers.recent_trades import render_recent_trades
from bot.handlers.reports import render_reports
from bot.handlers.settings import render_settings
from bot.handlers.trade_create import render_add_trade
from bot.keyboards.inline import (
    MENU_ACTIVE,
    MENU_ADD_TRADE,
    MENU_ALERTS,
    MENU_LEVERAGE,
    MENU_PENDING,
    MENU_RECENT,
    MENU_REPORTS,
    MENU_SETTINGS,
)
from bot.utils.formatting import safe_handler

# Registered FIRST in main.py: a bottom-menu tap must always work, even if the
# user is mid-flow somewhere else (typing an entry price, waiting for a
# screenshot, etc.) — this router intercepts those taps before any
# state-scoped handler in another router gets a chance to misinterpret them.
router = Router(name="menu")


@router.message(F.text == MENU_ADD_TRADE)
@safe_handler
async def menu_add_trade(message: Message, state: FSMContext) -> None:
    await state.clear()
    await render_add_trade(message, state)


@router.message(F.text == MENU_PENDING)
@safe_handler
async def menu_pending(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.clear()
    await render_pending(message, session, user)


@router.message(F.text == MENU_ACTIVE)
@safe_handler
async def menu_active(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.clear()
    await render_active(message, session, user)


@router.message(F.text == MENU_REPORTS)
@safe_handler
async def menu_reports(message: Message, state: FSMContext) -> None:
    await state.clear()
    await render_reports(message)


@router.message(F.text == MENU_LEVERAGE)
@safe_handler
async def menu_leverage(message: Message, state: FSMContext) -> None:
    await state.clear()
    await render_leverage(message, state)


@router.message(F.text == MENU_RECENT)
@safe_handler
async def menu_recent(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.clear()
    await render_recent_trades(message, session, user)


@router.message(F.text == MENU_ALERTS)
@safe_handler
async def menu_alerts(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    await state.clear()
    await render_alerts(message, session, user)


@router.message(F.text == MENU_SETTINGS)
@safe_handler
async def menu_settings(message: Message, state: FSMContext, user: User) -> None:
    await state.clear()
    await render_settings(message, user)
