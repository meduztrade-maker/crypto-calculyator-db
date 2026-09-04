from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import (
    TradeStateError,
    activate_trade,
    delete_trade,
    get_user_trade,
    list_pending_trades,
    miss_trade,
)
from bot.database.models import User
from bot.keyboards.inline import NavCB, TradeCB, TradeListItemCB, pending_detail_keyboard, pending_list_keyboard
from bot.utils.formatting import safe_handler, trade_card_pending

router = Router(name="pending")


async def _pending_list_content(session: AsyncSession, user: User):
    trades = await list_pending_trades(session, user)
    if not trades:
        return "⏳ Pending trade'lar yo'q.", None
    text = f"⏳ PENDING ({len(trades)} ta)\n\nBatafsil ko'rish uchun tanlang:"
    return text, pending_list_keyboard(trades)


async def render_pending(message: Message, session: AsyncSession, user: User) -> None:
    text, kb = await _pending_list_content(session, user)
    await message.answer(text, reply_markup=kb)


@router.callback_query(NavCB.filter(F.target == "pending"))
@safe_handler
async def back_to_pending(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    text, kb = await _pending_list_content(session, user)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(TradeListItemCB.filter(F.list_type == "pending"))
@safe_handler
async def pending_detail(callback: CallbackQuery, callback_data: TradeListItemCB, session: AsyncSession, user: User) -> None:
    trade = await get_user_trade(session, user, callback_data.trade_id)
    if trade is None or trade.status.value != "PENDING":
        await callback.answer("❌ Bu trade endi pending emas.", show_alert=True)
        text, kb = await _pending_list_content(session, user)
        await callback.message.edit_text(text, reply_markup=kb)
        return
    await callback.message.edit_text(trade_card_pending(trade), reply_markup=pending_detail_keyboard(trade.id))
    await callback.answer()


@router.callback_query(TradeCB.filter(F.action == "activate"))
@safe_handler
async def activate(callback: CallbackQuery, callback_data: TradeCB, session: AsyncSession, user: User) -> None:
    try:
        await activate_trade(session, user, callback_data.trade_id)
    except TradeStateError:
        await callback.answer("❌ Bu trade allaqachon boshqa holatda.", show_alert=True)
        return
    await callback.answer("✅ Active qilindi")
    text, kb = await _pending_list_content(session, user)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(TradeCB.filter(F.action == "miss"))
@safe_handler
async def miss(callback: CallbackQuery, callback_data: TradeCB, session: AsyncSession, user: User) -> None:
    try:
        await miss_trade(session, user, callback_data.trade_id)
    except TradeStateError:
        await callback.answer("❌ Bu trade allaqachon boshqa holatda.", show_alert=True)
        return
    await callback.answer("⚪ Missed deb belgilandi")
    text, kb = await _pending_list_content(session, user)
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(TradeCB.filter(F.action == "delete"))
@safe_handler
async def delete(callback: CallbackQuery, callback_data: TradeCB, session: AsyncSession, user: User) -> None:
    try:
        await delete_trade(session, user, callback_data.trade_id)
    except TradeStateError:
        await callback.answer("❌ Faqat pending trade'ni o'chirish mumkin.", show_alert=True)
        return
    await callback.answer("🗑 O'chirildi")
    text, kb = await _pending_list_content(session, user)
    await callback.message.edit_text(text, reply_markup=kb)
