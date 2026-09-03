from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from bot.database.crud import get_or_create_user
from bot.database.engine import async_session_maker


class DbSessionMiddleware(BaseMiddleware):
    """Opens one AsyncSession per update and attaches it + the resolved User to handler data."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session_maker() as session:
            data["session"] = session

            tg_user: TgUser | None = data.get("event_from_user")
            if tg_user is not None:
                data["user"] = await get_or_create_user(session, tg_user.id, tg_user.username)

            return await handler(event, data)
