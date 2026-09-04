"""
Central configuration. All secrets/config come from environment variables
(.env locally, Railway Variables in production) — nothing sensitive is
hardcoded, per spec section 24.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


def _to_asyncpg_url(url: str) -> str:
    """Normalize a postgres:// URL (as Railway gives it) to the asyncpg driver form."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(default_factory=lambda: _require("BOT_TOKEN"))
    database_url: str = field(default_factory=lambda: _to_asyncpg_url(_require("DATABASE_URL")))
    admin_id: int = field(default_factory=lambda: int(_require("ADMIN_ID")))
    backup_channel_id: int = field(default_factory=lambda: int(_require("BACKUP_CHANNEL_ID")))
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Tashkent"))
    default_margin: str = field(default_factory=lambda: os.getenv("DEFAULT_MARGIN", "500"))
    webapp_url: str | None = field(default_factory=lambda: os.getenv("WEBAPP_URL") or None)

    # Backup retention policy (spec section 21)
    daily_backup_retention_days: int = 30
    weekly_backup_retention_weeks: int = 12
    monthly_backup_retention_months: int = 12
    backup_hour_local: int = 3  # 03:00 local (Asia/Tashkent) daily backup


settings = Settings()
