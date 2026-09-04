from __future__ import annotations

import aiohttp

from bot.config import settings

_API_BASE = f"https://api.telegram.org/bot{settings.bot_token}"


async def send_photo_get_file_id(image_bytes: bytes, filename: str, chat_id: int, caption: str = "") -> str:
    """Uploads an image to Telegram (into the user's own chat with the bot) and returns its file_id,
    so trades created from the Mini App store screenshots the same way the bot conversation does."""
    form = aiohttp.FormData()
    form.add_field("chat_id", str(chat_id))
    if caption:
        form.add_field("caption", caption)
    form.add_field("photo", image_bytes, filename=filename, content_type="image/jpeg")

    async with aiohttp.ClientSession() as http:
        async with http.post(f"{_API_BASE}/sendPhoto", data=form) as resp:
            data = await resp.json()

    if not data.get("ok"):
        raise RuntimeError(f"Telegram sendPhoto failed: {data.get('description', data)}")

    photo_sizes = data["result"]["photo"]
    return photo_sizes[-1]["file_id"]
