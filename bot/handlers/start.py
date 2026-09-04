from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import NavCB, main_reply_keyboard

router = Router(name="start")

WELCOME_TEXT = (
    "📊 MEDUZ TRADING JOURNAL\n\n"
    "Pastdagi menyudan bo'lim tanlang 👇"
)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=main_reply_keyboard())


@router.callback_query(NavCB.filter(F.target == "cancel"))
async def cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()
