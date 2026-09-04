from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from bot.config import settings
from bot.keyboards.inline import NavCB, main_reply_keyboard

router = Router(name="start")

WELCOME_TEXT = (
    "📊 MEDUZ TRADING JOURNAL\n\n"
    "Pastdagi menyudan bo'lim tanlang 👇"
)


def _webapp_keyboard() -> InlineKeyboardMarkup | None:
    if not settings.webapp_url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🚀 Mini App ochish", web_app=WebAppInfo(url=settings.webapp_url))]]
    )


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=main_reply_keyboard())
    kb = _webapp_keyboard()
    if kb:
        await message.answer(
            "✨ Yangi: to'liq grafik va tezkor boshqaruv uchun Mini App'ni sinab ko'ring:",
            reply_markup=kb,
        )


@router.callback_query(NavCB.filter(F.target == "cancel"))
async def cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()
