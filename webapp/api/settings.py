from __future__ import annotations

import gzip
import tempfile
from pathlib import Path

from aiogram import Bot
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import add_margin_preset, delete_margin_preset, list_margin_presets, update_margin
from bot.database.models import User
from bot.services.backup import _restore_database_from_file, get_last_backup, restore_latest, run_backup
from webapp.deps import get_current_user, get_session
from webapp.schemas import BackupOut, MarginIn, MarginPresetIn, MarginPresetOut, MeOut

router = APIRouter(prefix="/api", tags=["settings"])


def get_bot(request: Request) -> Bot:
    return request.app.state.bot


def _require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Faqat admin uchun")


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)):
    return MeOut(telegram_id=user.telegram_id, username=user.username, margin=user.margin, timezone=user.timezone, is_admin=user.is_admin)


@router.post("/settings/margin", response_model=MeOut)
async def set_margin(body: MarginIn, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    if body.margin <= 0:
        raise HTTPException(status_code=422, detail="Margin musbat bo'lishi kerak")
    user = await update_margin(session, user, body.margin)
    return MeOut(telegram_id=user.telegram_id, username=user.username, margin=user.margin, timezone=user.timezone, is_admin=user.is_admin)


MAX_MARGIN_PRESETS = 5


@router.get("/settings/margins", response_model=list[MarginPresetOut])
async def get_margins(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return await list_margin_presets(session, user)


@router.post("/settings/margins", response_model=MarginPresetOut)
async def add_margin(body: MarginPresetIn, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    if body.amount <= 0:
        raise HTTPException(status_code=422, detail="Marja musbat bo'lishi kerak")
    label = body.label.strip()[:32]
    if not label:
        raise HTTPException(status_code=422, detail="Nom bo'sh bo'lmasin")
    existing = await list_margin_presets(session, user)
    if len(existing) >= MAX_MARGIN_PRESETS:
        raise HTTPException(status_code=422, detail=f"Ko'pi bilan {MAX_MARGIN_PRESETS} ta marja saqlash mumkin")
    return await add_margin_preset(session, user, label, body.amount)


@router.delete("/settings/margins/{preset_id}")
async def remove_margin(preset_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    ok = await delete_margin_preset(session, user, preset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return {"ok": True}


@router.post("/settings/backup/now")
async def backup_now(user: User = Depends(get_current_user), bot: Bot = Depends(get_bot)):
    _require_admin(user)
    backup = await run_backup(bot, manual=True)
    return {"status": backup.status.value}


@router.get("/settings/backup/last", response_model=BackupOut | None)
async def backup_last(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    _require_admin(user)
    backup = await get_last_backup(session)
    if backup is None:
        return None
    return BackupOut(backup_type=backup.backup_type.value, status=backup.status.value, created_at=backup.created_at)


@router.post("/settings/backup/restore")
async def backup_restore(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session), bot: Bot = Depends(get_bot)):
    _require_admin(user)
    try:
        backup = await restore_latest(bot, session)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))
    return {"restored_from": backup.created_at.isoformat()}


@router.post("/settings/backup/restore-upload")
async def backup_restore_upload(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Manual disaster-recovery path: admin uploads a previously downloaded
    backup file (.json or .json.gz, whatever the bot/Mini App produced)
    directly, bypassing the Telegram file_id round-trip entirely. Useful
    when moving to a brand-new database/hosting where no Backup row with
    a valid file_id exists yet (e.g. after a full redeploy).
    """
    _require_admin(user)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Bo'sh fayl")

    with tempfile.TemporaryDirectory() as tmp:
        json_path = Path(tmp) / "restore.json"
        try:
            if (file.filename or "").endswith(".gz") or data[:2] == b"\x1f\x8b":
                json_path.write_bytes(gzip.decompress(data))
            else:
                json_path.write_bytes(data)
            await _restore_database_from_file(session, str(json_path))
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Restore muvaffaqiyatsiz: {e}")

    return {"ok": True}
