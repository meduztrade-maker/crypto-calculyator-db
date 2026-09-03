from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import update_margin
from bot.database.models import User
from bot.keyboards.inline import BackupCB, NavCB, cancel_button, home_button, restore_confirm_keyboard, settings_menu
from bot.services.backup import get_last_backup, restore_latest, run_backup
from bot.states.trade_states import RestoreConfirm, SettingsFlow
from bot.utils.formatting import dec_str, parse_decimal, safe_handler

router = Router(name="settings")


@router.callback_query(NavCB.filter(F.target == "settings"))
@safe_handler
async def show_settings(callback: CallbackQuery, user: User) -> None:
    text = f"⚙️ SOZLAMALAR\n\n💵 Joriy margin: ${dec_str(user.margin)}"
    await callback.message.edit_text(text, reply_markup=settings_menu())
    await callback.answer()


@router.callback_query(NavCB.filter(F.target == "change_margin"))
@safe_handler
async def change_margin_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsFlow.margin)
    await callback.message.edit_text("💵 Yangi margin qiymatini kiriting ($):", reply_markup=cancel_button())
    await callback.answer()


@router.message(SettingsFlow.margin)
@safe_handler
async def margin_entered(message: Message, state: FSMContext, session: AsyncSession, user: User) -> None:
    value = parse_decimal(message.text)
    await update_margin(session, user, value)
    await state.clear()
    await message.answer(f"✅ Margin saqlandi: ${dec_str(value)}", reply_markup=home_button())


def _is_admin(user: User) -> bool:
    return user.is_admin


@router.callback_query(BackupCB.filter(F.action == "now"))
@safe_handler
async def backup_now(callback: CallbackQuery, bot: Bot, user: User) -> None:
    if not _is_admin(user):
        await callback.answer("❌ Faqat admin uchun.", show_alert=True)
        return
    await callback.answer("☁️ Backup boshlandi...")
    backup = await run_backup(bot, manual=True)
    status = "✅ Successful" if backup.status.value == "SUCCESS" else "❌ Failed"
    await callback.message.answer(f"☁️ MEDUZ JOURNAL BACKUP\n\nStatus: {status}", reply_markup=home_button())


@router.callback_query(BackupCB.filter(F.action == "last"))
@safe_handler
async def backup_last(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not _is_admin(user):
        await callback.answer("❌ Faqat admin uchun.", show_alert=True)
        return
    backup = await get_last_backup(session)
    if backup is None:
        await callback.message.edit_text("☁️ Hali backup qilinmagan.", reply_markup=home_button())
    else:
        await callback.message.edit_text(
            f"🕐 LAST BACKUP\n\n"
            f"Sana: {backup.created_at.strftime('%d.%m.%Y %H:%M UTC')}\n"
            f"Turi: {backup.backup_type.value}\n"
            f"Status: {'✅' if backup.status.value == 'SUCCESS' else '❌'} {backup.status.value}",
            reply_markup=home_button(),
        )
    await callback.answer()


@router.callback_query(BackupCB.filter(F.action == "restore"))
@safe_handler
async def restore_prompt(callback: CallbackQuery, state: FSMContext, user: User) -> None:
    if not _is_admin(user):
        await callback.answer("❌ Faqat admin uchun.", show_alert=True)
        return
    await state.set_state(RestoreConfirm.confirm)
    await callback.message.edit_text(
        "⚠️ Restore qilish barcha current database ma'lumotlarini backup bilan almashtirishi mumkin.\n\n"
        "Davom etasizmi?",
        reply_markup=restore_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(RestoreConfirm.confirm, BackupCB.filter(F.action == "restore_yes"))
@safe_handler
async def restore_confirmed(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession, user: User) -> None:
    if not _is_admin(user):
        await callback.answer("❌ Faqat admin uchun.", show_alert=True)
        return
    await state.clear()
    await callback.answer("🔄 Restore boshlandi...")
    try:
        backup = await restore_latest(bot, session)
        await callback.message.edit_text(
            f"✅ Restore muvaffaqiyatli.\n\nBackup sanasi: {backup.created_at.strftime('%d.%m.%Y %H:%M UTC')}",
            reply_markup=home_button(),
        )
    except Exception as e:  # noqa: BLE001
        await callback.message.edit_text(f"❌ Restore muvaffaqiyatsiz: {e}", reply_markup=home_button())


@router.callback_query(RestoreConfirm.confirm, BackupCB.filter(F.action == "restore_no"))
@safe_handler
async def restore_cancelled(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Restore bekor qilindi.", reply_markup=home_button())
    await callback.answer()
