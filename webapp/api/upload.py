from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from bot.database.models import User
from webapp.deps import get_current_user
from webapp.telegram_api import send_photo_get_file_id

router = APIRouter(prefix="/api/upload", tags=["upload"])

_MAX_BYTES = 10 * 1024 * 1024


@router.post("")
async def upload_screenshot(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=422, detail="Faqat rasm fayllari (jpg/png/webp)")
    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=422, detail="Rasm hajmi juda katta (max 10MB)")

    try:
        file_id = await send_photo_get_file_id(data, file.filename or "screenshot.jpg", user.telegram_id, caption="📸 Mini App orqali yuklangan screenshot")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Telegram'ga yuklashda xatolik: {e}")

    return {"file_id": file_id}
