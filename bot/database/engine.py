from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
