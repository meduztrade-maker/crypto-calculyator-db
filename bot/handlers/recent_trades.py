from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.database.crud import TradeStateError, force_delete_trade, list_recent_trades
from bot.database.models import User
from bot.keyboards.inline import NavCB, RecentTradeCB, home_button, recent_trade_confirm_keyboard, recent_trade_keyboard
from bot.utils.formatting import safe_handler, trade_card_generic
from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="recent_trades")


@router.callback_query(NavCB.filter(F.target == "recent_trades"))
@safe_handler
async def show_recent_trades(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    trades = await list_recent_trades(session, user, limit=5)
    if not trades:
        await callback.message.edit_text("🗑 Hali trade'lar yo'q.", reply_markup=home_button())
        await callback.answer()
        return

    await callback.message.edit_text("🗑 OXIRGI TRADELAR (5 tagacha)", reply_markup=home_button())
    for trade in trades:
        await callback.message.answer(trade_card_generic(trade), reply_markup=recent_trade_keyboard(trade.id))
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
    await callback.message.edit_text("🗑 Trade o'chirildi.", reply_markup=home_button())
    await callback.answer()
