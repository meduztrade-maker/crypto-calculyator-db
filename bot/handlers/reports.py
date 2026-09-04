from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.keyboards.inline import ReportCB, cancel_button, reports_menu
from bot.services.report_image import render_report_image
from bot.services.stats import compute_period_stats, current_week_bounds, custom_bounds, format_text_report, today_bounds
from bot.states.trade_states import CustomPeriod
from bot.utils.formatting import parse_date, safe_handler

router = Router(name="reports")


async def render_reports(message: Message) -> None:
    await message.answer("📊 Hisobot turini tanlang:", reply_markup=reports_menu())


async def _send_report(target: Message, session: AsyncSession, user: User, title: str, start, end) -> None:
    stats = await compute_period_stats(session, user, start, end)
    text = format_text_report(title, stats)
    await target.answer(text)

    image_bytes = render_report_image(title, stats)
    await target.answer_photo(
        BufferedInputFile(image_bytes, filename="meduz_report.png"),
        caption="🖼 Ulashish uchun tayyor rasm",
    )


@router.callback_query(ReportCB.filter(F.period == "daily"))
@safe_handler
async def daily_report(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    start, end = today_bounds()
    await _send_report(callback.message, session, user, "DAILY PERFORMANCE", start, end)
    await callback.answer()


@router.callback_query(ReportCB.filter(F.period == "weekly"))
@safe_handler
async def weekly_report(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    start, end = current_week_bounds()
    await _send_report(callback.message, session, user, "WEEKLY PERFORMANCE", start, end)
    await callback.answer()


@router.callback_query(ReportCB.filter(F.period == "custom"))
@safe_handler
async def custom_report_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CustomPeriod.start_date)
    await callback.message.edit_text("📅 Boshlanish sanasini kiriting:\n\nFormat: DD.MM.YYYY", reply_markup=cancel_button())
    await callback.answer()


@router.message(CustomPeriod.start_date)
@safe_handler
async def custom_report_start_date(message: Message, state: FSMContext) -> None:
    start = parse_date(message.text)
    await state.update_data(start_date=start.isoformat())
    await state.set_state(CustomPeriod.end_date)
    await message.answer("📅 Tugash sanasini kiriting:\n\nFormat: DD.MM.YYYY", reply_markup=cancel_button())


@router.message(CustomPeriod.end_date)
@safe_handler
async def custom_report_end_date(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    from datetime import datetime

    end = parse_date(message.text)
    data = await state.get_data()
    start = datetime.fromisoformat(data["start_date"])
    await state.clear()

    start_utc, end_utc = custom_bounds(start, end)
    title = f"{start.strftime('%d.%m.%Y')} — {end.strftime('%d.%m.%Y')}"
    await _send_report(message, session, user, title, start_utc, end_utc)
