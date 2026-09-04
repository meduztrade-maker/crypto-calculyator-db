from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import get_or_create_user
from bot.database.engine import async_session_maker
from bot.database.models import User
from webapp.auth import TelegramUser, get_telegram_user


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_current_user(
    tg_user: TelegramUser = Depends(get_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    return await get_or_create_user(session, tg_user.id, tg_user.username)
