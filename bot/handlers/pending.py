from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.database.crud import TradeStateError, activate_trade, delete_trade, list_pending_trades, miss_trade
from bot.database.models import User
from bot.keyboards.inline import NavCB, TradeCB, active_trade_keyboard, home_button, pending_trade_keyboard
from bot.utils.formatting import safe_handler, trade_card_active, trade_card_missed, trade_card_pending
from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="pending")


@router.callback_query(NavCB.filter(F.target == "pending"))
@safe_handler
async def show_pending(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    trades = await list_pending_trades(session, user)
    if not trades:
        await callback.message.edit_text("⏳ Pending trade'lar yo'q.", reply_markup=home_button())
        await callback.answer()
        return

    await callback.message.edit_text(f"⏳ PENDING ({len(trades)} ta)", reply_markup=home_button())
    for trade in trades:
        await callback.message.answer(trade_card_pending(trade), reply_markup=pending_trade_keyboard(trade.id))
    await callback.answer()


@router.callback_query(TradeCB.filter(F.action == "activate"))
@safe_handler
async def activate(callback: CallbackQuery, callback_data: TradeCB, session: AsyncSession, user: User) -> None:
    try:
        trade = await activate_trade(session, user, callback_data.trade_id)
    except TradeStateError:
        await callback.answer("❌ Bu trade allaqachon boshqa holatda.", show_alert=True)
        return
    await callback.message.edit_text(trade_card_active(trade), reply_markup=active_trade_keyboard(trade.id))
    await callback.answer("✅ Active qilindi")


@router.callback_query(TradeCB.filter(F.action == "miss"))
@safe_handler
async def miss(callback: CallbackQuery, callback_data: TradeCB, session: AsyncSession, user: User) -> None:
    try:
        trade = await miss_trade(session, user, callback_data.trade_id)
    except TradeStateError:
        await callback.answer("❌ Bu trade allaqachon boshqa holatda.", show_alert=True)
        return
    await callback.message.edit_text(trade_card_missed(trade), reply_markup=home_button())
    await callback.answer()


@router.callback_query(TradeCB.filter(F.action == "delete"))
@safe_handler
async def delete(callback: CallbackQuery, callback_data: TradeCB, session: AsyncSession, user: User) -> None:
    try:
        await delete_trade(session, user, callback_data.trade_id)
    except TradeStateError:
        await callback.answer("❌ Faqat pending trade'ni o'chirish mumkin.", show_alert=True)
        return
    await callback.message.edit_text("🗑 Trade o'chirildi.", reply_markup=home_button())
    await callback.answer()
