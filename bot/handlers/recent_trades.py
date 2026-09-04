from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import TradeStateError, force_delete_trade, get_user_trade, list_recent_trades
from bot.database.models import User
from bot.keyboards.inline import (
    NavCB,
    RecentTradeCB,
    TradeListItemCB,
    recent_list_keyboard,
    recent_trade_confirm_keyboard,
    recent_trade_detail_keyboard,
)
from bot.utils.formatting import safe_handler, trade_card_generic

router = Router(name="recent_trades")


async def _recent_list_content(session: AsyncSession, user: User):
    trades = await list_recent_trades(session, user, limit=5)
    if not trades:
        return "🗑 Hali trade'lar yo'q.", None
    text = "🗑 OXIRGI TRADELAR (5 tagacha)\n\nBatafsil ko'rish uchun tanlang:"
    return text, recent_list_keyboard(trades)


async def render_recent_trades(message: Message, session: AsyncSession, user: User) -> None:
    text, kb = await _recent_list_content(session, user)
    await message.answer(text, reply_markup=kb)


@router.callback_query(NavCB.filter(F.target == "recent_trades"))
@safe_handler
async def back_to_recent(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    text, kb = await _recent_list_content(session, user)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(TradeListItemCB.filter(F.list_type == "recent"))
@safe_handler
async def recent_detail(callback: CallbackQuery, callback_data: TradeListItemCB, session: AsyncSession, user: User) -> None:
    trade = await get_user_trade(session, user, callback_data.trade_id)
    if trade is None:
        await callback.answer("❌ Trade topilmadi.", show_alert=True)
        text, kb = await _recent_list_content(session, user)
        await callback.message.edit_text(text, reply_markup=kb)
        return
    await callback.message.edit_text(trade_card_generic(trade), reply_markup=recent_trade_detail_keyboard(trade.id))
    await callback.answer()


@router.callback_query(RecentTradeCB.filter(F.action == "delete"))
@safe_handler
async def confirm_delete(callback: CallbackQuery, callback_data: RecentTradeCB) -> None:
    await callback.message.edit_text(
        "⚠️ Ushbu trade butunlay o'chiriladi (journal tarixidan ham).\n\nDavom etasizmi?",
        reply_markup=recent_trade_confirm_keyboard(callback_data.trade_id),
    )
    await callback.answer()


@router.callback_query(RecentTradeCB.filter(F.action == "confirm_delete"))
@safe_handler
async def do_delete(callback: CallbackQuery, callback_data: RecentTradeCB, session: AsyncSession, user: User) -> None:
    try:
        await force_delete_trade(session, user, callback_data.trade_id)
    except TradeStateError:
        await callback.answer("❌ Trade topilmadi.", show_alert=True)
        return
    await callback.answer("🗑 O'chirildi")
    text, kb = await _recent_list_content(session, user)
    await callback.message.edit_text(text, reply_markup=kb)
