from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from bot.config import settings

logger = logging.getLogger(__name__)

CHECK_SUB_CALLBACK = "check_subscription"

_SUBSCRIBED_STATUSES = ("member", "administrator", "creator")


def subscribe_keyboard() -> InlineKeyboardMarkup:
    channel = (settings.required_channel or "").lstrip("@")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=f"https://t.me/{channel}")],
            [InlineKeyboardButton(text="✅ Tekshirish", callback_data=CHECK_SUB_CALLBACK)],
        ]
    )


GATE_TEXT = (
    "🔒 Botdan foydalanish uchun avval quyidagi kanalga obuna bo'ling, "
    "so'ng \"✅ Tekshirish\" tugmasini bosing."
)


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if not settings.required_channel:
        return True
    try:
        member = await bot.get_chat_member(chat_id=settings.required_channel, user_id=user_id)
        return member.status in _SUBSCRIBED_STATUSES
    except TelegramBadRequest:
        # Most likely cause: the bot isn't an admin of the channel yet, or
        # the channel username is wrong. Fail OPEN rather than lock every
        # single user out of the bot over a config mistake only the bot
        # owner can fix - a broken gate should never become a broken bot.
        logger.warning(
            "Could not verify subscription for user %s in %s - letting them through "
            "(is the bot an admin of that channel?)",
            user_id, settings.required_channel,
        )
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error checking subscription for user %s", user_id)
        return True


class SubscriptionMiddleware(BaseMiddleware):
    """Blocks every update until the user has joined settings.required_channel.
    No-ops entirely when REQUIRED_CHANNEL isn't set. Registered before
    DbSessionMiddleware so a gated user never triggers a DB session at all."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not settings.required_channel:
            return await handler(event, data)

        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        # The "Tekshirish" button's own callback must always reach its
        # handler (in bot/handlers/start.py) - otherwise a gated user could
        # never re-verify and would be stuck forever.
        if isinstance(event, CallbackQuery) and event.data == CHECK_SUB_CALLBACK:
            return await handler(event, data)

        bot: Bot = data["bot"]
        if await is_subscribed(bot, user.id):
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(GATE_TEXT, reply_markup=subscribe_keyboard())
        elif isinstance(event, CallbackQuery):
            await event.answer("Avval kanalga obuna bo'ling.", show_alert=True)
        return None
