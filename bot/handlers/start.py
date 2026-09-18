from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from bot.config import settings
from bot.keyboards.inline import NavCB, main_reply_keyboard

router = Router(name="start")

WELCOME_TEXT = (
    "📊 <b>MEDUZ TRADING JOURNAL</b>\n\n"
    "Professional crypto trading journal — tradelaringizni yuriting, statistika ko'ring, narx alertlari qo'ying.\n\n"
    "Pastdagi menyudan bo'lim tanlang 👇\n"
    "Har qanday paytda <b>/help</b> yozib to'liq qo'llanmani ko'rishingiz mumkin."
)

HELP_TEXT = (
    "📖 <b>MEDUZ TRADING JOURNAL — QO'LLANMA</b>\n\n"
    "<b>➕ Trade qo'shish</b>\n"
    "Coin, yo'nalish (LONG/SHORT), risk %, Entry va SL narxini ketma-ket kiritasiz, so'ngida screenshot "
    "yuborasiz (xohlasangiz o'tkazib yuborsa ham bo'ladi). Trade <b>PENDING</b> holatida saqlanadi.\n\n"
    "<b>⏳ Pending</b>\n"
    "Hali faollashmagan (limit order kutilayotgan) tradelar ro'yxati. Har birini tanlab:\n"
    "🟢 Activate — limit order ishlagach\n"
    "⚪ Missed — narx kelmay qolsa\n"
    "🗑 Delete — butunlay o'chirish\n\n"
    "<b>🟢 Active</b>\n"
    "Hozir ochiq tradelaringiz. Yopish uchun tanlang:\n"
    "🛑 SL — avtomatik -1R\n"
    "🟡 B/U yoki 🟢 TP — RR qiymatini kiritasiz\n"
    "Barchasida yopilgandan keyingi screenshot so'raladi.\n\n"
    "<b>📊 Hisobot</b>\n"
    "Kunlik / Haftalik / Davr — to'liq statistika: equity curve, Win Rate, Profit Factor, Max Drawdown, "
    "g'alaba/zarar ketma-ketligi.\n"
    "Kalendar — har kunning R natijasi rangli kalendar ko'rinishida (🟢 foyda, 🔴 zarar), kunni bosib "
    "o'sha kungi tradelarni ko'rish mumkin.\n\n"
    "<b>🧮 Leverage Calculator</b>\n"
    "Entry-SL masofasi (%) va risk summasini ($) kiriting — kerakli leverage avtomatik hisoblanadi.\n\n"
    "<b>🗑 Oxirgi tradelar</b>\n"
    "Oxirgi 5 ta trade (statusidan qat'i nazar) — xato kiritilgan trade'ni butunlay o'chirish uchun.\n\n"
    "<b>🔔 Alert</b>\n"
    "Coin nomi va maqsadli narxni kiriting — narx yetganda darhol Telegram xabari yuboriladi. Alertni "
    "bosib jonli (real-time) grafikni ham kuzatishingiz mumkin.\n\n"
    "<b>⚙️ Sozlamalar</b>\n"
    "Margin qiymatini o'zgartirish, va (faqat admin uchun) ma'lumotlar bazasi backup/restore qilish.\n\n"
    "<b>🚀 Mini App</b>\n"
    "To'liq grafik, kalendar va tezkorroq boshqaruv uchun pastdagi matn maydoni yonidagi menyu tugmasini "
    "yoki /start xabaridagi \"Mini App ochish\" tugmasini bosing.\n\n"
    "Savol tug'ilsa, istalgan vaqt <b>/help</b> yozing — bu xabar qayta chiqadi."
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


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.callback_query(NavCB.filter(F.target == "cancel"))
async def cancel_flow(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()
