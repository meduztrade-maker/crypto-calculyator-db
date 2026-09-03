from __future__ import annotations

import gzip
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.types import BufferedInputFile, FSInputFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.engine import async_session_maker
from bot.database.models import Backup, BackupStatus, BackupType

logger = logging.getLogger("meduz_bot")


def _plain_pg_url() -> str:
    """pg_dump needs a libpq-style URL, not the SQLAlchemy asyncpg driver URL."""
    url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def _dump_database_to_file(dest_path: str) -> None:
    """
    Shells out to pg_dump. Requires the `postgresql-client` package to be present
    in the deployment image (see nixpacks.toml — installed there for Railway).
    """
    url = _plain_pg_url()
    result = subprocess.run(
        ["pg_dump", "--no-owner", "--no-privileges", "-Fc", "-f", dest_path, url],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr[-2000:]}")


def _restore_database_from_file(src_path: str) -> None:
    url = _plain_pg_url()
    result = subprocess.run(
        ["pg_restore", "--no-owner", "--no-privileges", "--clean", "--if-exists", "-d", url, src_path],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pg_restore failed: {result.stderr[-2000:]}")


def _backup_types_for(now: datetime) -> list[BackupType]:
    types = [BackupType.DAILY]
    if now.weekday() == 0:  # Monday
        types.append(BackupType.WEEKLY)
    if now.day == 1:
        types.append(BackupType.MONTHLY)
    return types


async def run_backup(bot: Bot, *, manual: bool = False) -> Backup:
    """Dumps the DB, gzips it, uploads it to the private backup channel, records it, and purges old backups."""
    now = datetime.now(timezone.utc)
    file_name = f"backup_{now.strftime('%Y-%m-%d_%H-%M')}.sql.gz"

    with tempfile.TemporaryDirectory() as tmp:
        dump_path = os.path.join(tmp, "dump.sql")
        gz_path = os.path.join(tmp, file_name)
        try:
            _dump_database_to_file(dump_path)
            with open(dump_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                f_out.writelines(f_in)

            caption = (
                "☁️ MEDUZ JOURNAL BACKUP\n\n"
                f"Date: {now.strftime('%d.%m.%Y %H:%M UTC')}\n"
                "Database: PostgreSQL\n"
                "Status: ✅ Successful"
            )
            msg = await bot.send_document(
                chat_id=settings.backup_channel_id,
                document=FSInputFile(gz_path, filename=file_name),
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
        gz_path = os.path.join(tmp, row.file_name)
        dump_path = os.path.join(tmp, "restore.sql")
        await bot.download(row.telegram_file_id, destination=gz_path)
        with gzip.open(gz_path, "rb") as f_in, open(dump_path, "wb") as f_out:
            f_out.writelines(f_in)
        _restore_database_from_file(dump_path)

    return row
