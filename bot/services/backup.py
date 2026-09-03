from __future__ import annotations

import enum
import gzip
import json
import logging
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import BufferedInputFile
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.engine import async_session_maker
from bot.database.models import Backup, BackupStatus, BackupType, Trade, User

logger = logging.getLogger("meduz_bot")

DUMP_VERSION = 1


# ---------------------------------------------------------------------------
# JSON encode/decode helpers (Decimal / datetime / enum aware)
# ---------------------------------------------------------------------------

def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return {"__decimal__": str(obj)}
    if isinstance(obj, datetime):
        return {"__datetime__": obj.isoformat()}
    if isinstance(obj, date):
        return {"__date__": obj.isoformat()}
    if isinstance(obj, enum.Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _json_object_hook(d: dict) -> Any:
    if "__decimal__" in d:
        return Decimal(d["__decimal__"])
    if "__datetime__" in d:
        return datetime.fromisoformat(d["__datetime__"])
    if "__date__" in d:
        return date.fromisoformat(d["__date__"])
    return d


def _row_to_dict(obj, columns: list[str]) -> dict:
    return {col: getattr(obj, col) for col in columns}


USER_COLUMNS = ["id", "telegram_id", "username", "margin", "timezone", "is_admin", "created_at"]
TRADE_COLUMNS = [
    "id", "user_id", "coin", "direction", "status", "risk_percent", "entry_price",
    "stop_loss_price", "stop_distance_percent", "result_type", "result_rr",
    "opening_screenshot_file_id", "closing_screenshot_file_id",
    "created_at", "activated_at", "closed_at", "missed_at",
]


# ---------------------------------------------------------------------------
# Dump / restore (pure Python — works in any deploy environment)
# ---------------------------------------------------------------------------

async def _dump_database_to_file(session: AsyncSession, dest_path: str) -> None:
    users = (await session.execute(select(User).order_by(User.id))).scalars().all()
    trades = (await session.execute(select(Trade).order_by(Trade.id))).scalars().all()

    payload = {
        "version": DUMP_VERSION,
        "exported_at": datetime.now(timezone.utc),
        "users": [_row_to_dict(u, USER_COLUMNS) for u in users],
        "trades": [_row_to_dict(t, TRADE_COLUMNS) for t in trades],
    }

    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, default=_json_default, ensure_ascii=False)


async def _restore_database_from_file(session: AsyncSession, src_path: str) -> None:
    with open(src_path, "r", encoding="utf-8") as f:
        payload = json.load(f, object_hook=_json_object_hook)

    async with session.begin():
        # Trades first (FK -> users), then users, to respect referential integrity while clearing.
        await session.execute(delete(Trade))
        await session.execute(delete(User))

        for u in payload["users"]:
            await session.execute(
                text(
                    "INSERT INTO users (id, telegram_id, username, margin, timezone, is_admin, created_at) "
                    "VALUES (:id, :telegram_id, :username, :margin, :timezone, :is_admin, :created_at)"
                ),
                u,
            )
        for t in payload["trades"]:
            await session.execute(
                text(
                    "INSERT INTO trades (id, user_id, coin, direction, status, risk_percent, entry_price, "
                    "stop_loss_price, stop_distance_percent, result_type, result_rr, "
                    "opening_screenshot_file_id, closing_screenshot_file_id, "
                    "created_at, activated_at, closed_at, missed_at) "
                    "VALUES (:id, :user_id, :coin, :direction, :status, :risk_percent, :entry_price, "
                    ":stop_loss_price, :stop_distance_percent, :result_type, :result_rr, "
                    ":opening_screenshot_file_id, :closing_screenshot_file_id, "
                    ":created_at, :activated_at, :closed_at, :missed_at)"
                ),
                t,
            )

        # Realign auto-increment sequences with the restored max ids.
        await session.execute(text(
            "SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE((SELECT MAX(id) FROM users), 1))"
        ))
        await session.execute(text(
            "SELECT setval(pg_get_serial_sequence('trades', 'id'), COALESCE((SELECT MAX(id) FROM trades), 1))"
        ))


def _backup_types_for(now: datetime) -> list[BackupType]:
    types = [BackupType.DAILY]
    if now.weekday() == 0:  # Monday
        types.append(BackupType.WEEKLY)
    if now.day == 1:
        types.append(BackupType.MONTHLY)
    return types


async def run_backup(bot: Bot, *, manual: bool = False) -> Backup:
    """Dumps users+trades to JSON, gzips it, uploads to the private backup channel, records it, purges old ones."""
    now = datetime.now(timezone.utc)
    file_name = f"backup_{now.strftime('%Y-%m-%d_%H-%M')}.json.gz"

    async with async_session_maker() as dump_session:
        with tempfile.TemporaryDirectory() as tmp:
            dump_path = Path(tmp) / "dump.json"
            gz_path = Path(tmp) / file_name
            try:
                await _dump_database_to_file(dump_session, str(dump_path))
                with open(dump_path, "rb") as f_in:
                    gz_path.write_bytes(gzip.compress(f_in.read()))

                caption = (
                    "☁️ MEDUZ JOURNAL BACKUP\n\n"
                    f"Date: {now.strftime('%d.%m.%Y %H:%M UTC')}\n"
                    "Database: PostgreSQL (JSON dump)\n"
                    "Status: ✅ Successful"
                )
                msg = await bot.send_document(
                    chat_id=settings.backup_channel_id,
                    document=BufferedInputFile(gz_path.read_bytes(), filename=file_name),
                    caption=caption,
                )
                status = BackupStatus.SUCCESS
                message_id = msg.message_id
                file_id = msg.document.file_id
            except Exception:
                logger.exception("Backup failed")
                status = BackupStatus.FAILED
                message_id = None
                file_id = None
                try:
                    await bot.send_message(
                        settings.backup_channel_id,
                        f"☁️ MEDUZ JOURNAL BACKUP\n\nDate: {now.strftime('%d.%m.%Y %H:%M UTC')}\n"
                        "Database: PostgreSQL\nStatus: ❌ Failed",
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Could not notify backup channel of failure")

    async with async_session_maker() as session:
        types = [BackupType.MANUAL] if manual else _backup_types_for(now)
        last_row: Backup | None = None
        for backup_type in types:
            row = Backup(
                backup_type=backup_type,
                telegram_message_id=message_id,
                telegram_file_id=file_id,
                file_name=file_name,
                status=status,
            )
            session.add(row)
            last_row = row
        await session.commit()
        if last_row:
            await session.refresh(last_row)

        if status == BackupStatus.SUCCESS and not manual:
            await _apply_retention(bot, session)

        return last_row


async def _apply_retention(bot: Bot, session: AsyncSession) -> None:
    """Purges old tiered backups per spec section 21, but never deletes the latest successful backup."""
    latest = await session.execute(
        select(Backup)
        .where(Backup.status == BackupStatus.SUCCESS)
        .order_by(Backup.created_at.desc())
        .limit(1)
    )
    protected = latest.scalar_one_or_none()
    protected_id = protected.id if protected else None

    now = datetime.now(timezone.utc)
    thresholds = {
        BackupType.DAILY: now - timedelta(days=settings.daily_backup_retention_days),
        BackupType.WEEKLY: now - timedelta(weeks=settings.weekly_backup_retention_weeks),
        BackupType.MONTHLY: now - timedelta(days=30 * settings.monthly_backup_retention_months),
    }

    for backup_type, cutoff in thresholds.items():
        old_rows = await session.execute(
            select(Backup).where(
                Backup.backup_type == backup_type,
                Backup.created_at < cutoff,
            )
        )
        for row in old_rows.scalars().all():
            if row.id == protected_id:
                continue
            if row.telegram_message_id:
                try:
                    await bot.delete_message(settings.backup_channel_id, row.telegram_message_id)
                except Exception:  # noqa: BLE001
                    logger.warning("Could not delete backup message %s (may already be gone)", row.telegram_message_id)
            await session.delete(row)
    await session.commit()


async def get_last_backup(session: AsyncSession) -> Backup | None:
    result = await session.execute(
        select(Backup).order_by(Backup.created_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def restore_latest(bot: Bot, session: AsyncSession) -> Backup:
    """Downloads the most recent successful backup via its stored file_id and restores it into Postgres."""
    result = await session.execute(
        select(Backup)
        .where(Backup.status == BackupStatus.SUCCESS)
        .order_by(Backup.created_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None or row.telegram_file_id is None:
        raise RuntimeError("No successful backup available to restore from")

    with tempfile.TemporaryDirectory() as tmp:
        gz_path = Path(tmp) / row.file_name
        dump_path = Path(tmp) / "restore.json"
        await bot.download(row.telegram_file_id, destination=str(gz_path))
        dump_path.write_bytes(gzip.decompress(gz_path.read_bytes()))
        await _restore_database_from_file(session, str(dump_path))

    return row
