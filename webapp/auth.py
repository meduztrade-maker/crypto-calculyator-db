from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

from bot.config import settings

MAX_INIT_DATA_AGE_SECONDS = 24 * 60 * 60  # 1 day — generous, since the mini app may stay open a while


class TelegramUser:
    __slots__ = ("id", "username", "first_name", "last_name", "is_premium")

    def __init__(self, id: int, username: str | None, first_name: str, last_name: str | None, is_premium: bool):
        self.id = id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.is_premium = is_premium


def _validate_init_data(init_data: str) -> dict:
    """
    Verifies the initData string Telegram's WebApp JS SDK provides, per the
    official algorithm: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    Raises HTTPException(401) on any failure.
    """
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing Telegram init data")

    pairs = dict(parse_qsl(init_data, strict_parsing=False))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash in init data")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))

    secret_key = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=401, detail="Invalid init data signature")

    auth_date = pairs.get("auth_date")
    if auth_date and (time.time() - int(auth_date)) > MAX_INIT_DATA_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Init data expired")

    return pairs


def parse_telegram_user(init_data: str) -> TelegramUser:
    pairs = _validate_init_data(init_data)
    user_raw = pairs.get("user")
    if not user_raw:
        raise HTTPException(status_code=401, detail="Missing user in init data")
    try:
        u = json.loads(user_raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Malformed user in init data")

    return TelegramUser(
        id=u["id"],
        username=u.get("username"),
        first_name=u.get("first_name", ""),
        last_name=u.get("last_name"),
        is_premium=bool(u.get("is_premium", False)),
    )


async def get_telegram_user(x_telegram_init_data: str = Header(default="")) -> TelegramUser:
    """FastAPI dependency: validates the X-Telegram-Init-Data header sent by the frontend."""
    return parse_telegram_user(x_telegram_init_data)
