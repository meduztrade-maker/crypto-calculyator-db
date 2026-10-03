from __future__ import annotations

import csv
import io

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import list_all_closed_trades
from bot.database.models import User
from bot.utils.formatting import dec_str, safe_handler

router = Router(name="export")

CSV_COLUMNS = [
    "coin", "direction", "entry_price", "stop_loss_price", "risk_percent",
    "result_type", "result_rr", "setup_tag", "emotion_tag", "closed_at",
]


def _trades_to_csv(trades) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for t in trades:
        writer.writerow([
            t.coin,
            t.direction.value,
            dec_str(t.entry_price),
            dec_str(t.stop_loss_price),
            dec_str(t.risk_percent),
            t.result_type.value if t.result_type else "",
            dec_str(t.result_rr) if t.result_rr is not None else "",
            t.setup_tag or "",
            t.emotion_tag or "",
            t.closed_at.strftime("%Y-%m-%d %H:%M") if t.closed_at else "",
        ])
    return buf.getvalue().encode("utf-8-sig")  # BOM so Excel opens UTF-8 (Uzbek text) correctly


@router.message(Command("export"))
@safe_handler
async def export_trades(message: Message, session: AsyncSession, user: User) -> None:
    trades = await list_all_closed_trades(session, user)
    if not trades:
        await message.answer("📤 Export qilish uchun yopilgan trade yo'q.")
        return

    csv_bytes = _trades_to_csv(trades)
    filename = f"meduz_trades_{message.date.strftime('%Y%m%d')}.csv"
    await message.answer_document(
        BufferedInputFile(csv_bytes, filename=filename),
        caption=f"📤 {len(trades)} ta yopilgan trade eksport qilindi.",
    )
