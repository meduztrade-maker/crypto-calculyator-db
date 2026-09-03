from __future__ import annotations

import io
import os

from PIL import Image, ImageDraw, ImageFont

from bot.services.stats import PeriodStats, format_coin_line
from bot.utils.formatting import dec_str

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "fonts")

_BG = (13, 17, 23)
_CARD = (22, 27, 34)
_GREEN = (63, 185, 80)
_RED = (248, 81, 73)
_GRAY = (139, 148, 158)
_WHITE = (240, 246, 252)
_ACCENT = (88, 166, 255)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(_ASSETS_DIR, name), size)


def _result_color(line: str) -> tuple[int, int, int]:
    if "SL" in line:
        return _RED
    if line.strip().endswith("R") and "+" in line:
        return _GREEN
    return _GRAY


def render_report_image(title: str, stats: PeriodStats) -> bytes:
    width = 900
    padding = 48
    coin_lines = [format_coin_line(c) for c in stats.coins][:12]
    height = 560 + max(0, len(coin_lines) - 1) * 40

    img = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(img)

    bold_xl = _font("DejaVuSans-Bold.ttf", 54)
    bold_lg = _font("DejaVuSans-Bold.ttf", 34)
    bold_md = _font("DejaVuSans-Bold.ttf", 26)
    regular_sm = _font("DejaVuSans.ttf", 20)
    regular_md = _font("DejaVuSans.ttf", 24)

    y = padding
    draw.text((padding, y), "MEDUZ", font=bold_lg, fill=_ACCENT)
    y += 48
    draw.text((padding, y), title, font=regular_md, fill=_GRAY)
    y += 56

    total_color = _GREEN if stats.total_r >= 0 else _RED
    total_str = f"{'+' if stats.total_r >= 0 else ''}{dec_str(stats.total_r)}R"
    draw.text((padding, y), total_str, font=bold_xl, fill=total_color)
    y += 90

    # Stat chips
    chip_data = [
        ("Win Rate", f"{stats.win_rate}%"),
        ("Average RR", f"{dec_str(stats.average_rr)}R"),
        ("Trades", str(stats.total_trades)),
    ]
    chip_w = (width - padding * 2 - 24) // 3
    for i, (label, value) in enumerate(chip_data):
        x0 = padding + i * (chip_w + 12)
        draw.rounded_rectangle([x0, y, x0 + chip_w, y + 110], radius=16, fill=_CARD)
        draw.text((x0 + 20, y + 18), label, font=regular_sm, fill=_GRAY)
        draw.text((x0 + 20, y + 50), value, font=bold_md, fill=_WHITE)
    y += 140

    draw.line([(padding, y), (width - padding, y)], fill=_CARD, width=3)
    y += 30

    for line in coin_lines:
        color = _result_color(line)
        draw.text((padding, y), line, font=regular_md, fill=color)
        y += 40

    y += 10
    draw.line([(padding, y), (width - padding, y)], fill=_CARD, width=3)
    y += 30
    draw.text((padding, y), "MEDUZ TRADING JOURNAL", font=regular_sm, fill=_GRAY)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
