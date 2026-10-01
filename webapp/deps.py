from __future__ import annotations

from typing import AsyncGenerator

from aiogram import Bot
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import get_or_create_user
from bot.database.engine import async_session_maker
from bot.database.models import User
from bot.middlewares.subscription import is_subscribed
from webapp.auth import TelegramUser, get_telegram_user


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_current_user(
    request: Request,
    tg_user: TelegramUser = Depends(get_telegram_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Every route in the app depends on this, so this is also where the
    subscription gate is enforced server-side - the frontend's own
    /api/subscription-status check is for a clean UX, this is what makes
    the gate actually real even if someone skips the frontend check."""
    bot: Bot = request.app.state.bot
    if not await is_subscribed(bot, tg_user.id):
        raise HTTPException(status_code=403, detail="not_subscribed")
    return await get_or_create_user(session, tg_user.id, tg_user.username)
