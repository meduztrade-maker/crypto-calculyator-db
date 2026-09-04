from __future__ import annotations

import io
import os
from decimal import Decimal

from PIL import Image, ImageDraw, ImageFont

from bot.services.stats import PeriodStats, format_coin_line
from bot.utils.formatting import dec_str

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "fonts")

_BG = (11, 15, 20)
_CARD = (19, 24, 31)
_CARD_BORDER = (32, 39, 49)
_GRID = (36, 43, 53)
_GREEN = (46, 204, 113)
_GREEN_DIM = (30, 90, 60)
_RED = (239, 68, 68)
_RED_DIM = (90, 35, 35)
_GRAY = (139, 148, 158)
_WHITE = (237, 242, 247)
_ACCENT = (88, 166, 255)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(_ASSETS_DIR, name), size)


def _bold(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSans-Bold.ttf", size)


def _regular(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSans.ttf", size)


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    return draw.textlength(text, font=font)


def _rounded_card(draw: ImageDraw.ImageDraw, box, radius=18, fill=_CARD, outline=_CARD_BORDER, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _result_color(result_type: str, rr) -> tuple:
    if result_type == "SL":
        return _RED
    if rr is not None and rr > 0:
        return _GREEN
    return _GRAY


# ---------------------------------------------------------------------------
# Equity curve panel — the main "pro trading dashboard" visual
# ---------------------------------------------------------------------------

def _draw_equity_curve(base: Image.Image, box, curve: list[Decimal]) -> None:
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(base)
    _rounded_card(draw, box)

    label_font = _regular(18)
    title_font = _bold(20)
    draw.text((x0 + 24, y0 + 18), "EQUITY CURVE (R)", font=title_font, fill=_WHITE)

    chart_top = y0 + 60
    chart_bottom = y1 - 30
    chart_left = x0 + 24
    chart_right = x1 - 70

    if not curve:
        draw.text(
            ((chart_left + chart_right) // 2 - 90, (chart_top + chart_bottom) // 2 - 10),
            "Yopilgan trade yo'q", font=label_font, fill=_GRAY,
        )
        return

    values = [Decimal("0")] + curve
    vmax = max(values)
    vmin = min(values)
    if vmax == vmin:
        vmax += Decimal("1")
        vmin -= Decimal("1")
    span = vmax - vmin
    pad = span * Decimal("0.15") or Decimal("1")
    vmax += pad
    vmin -= pad
    span = vmax - vmin

    def y_for(v: Decimal) -> float:
        return chart_bottom - float((v - vmin) / span) * (chart_bottom - chart_top)

    def x_for(i: int) -> float:
        if len(values) == 1:
            return chart_left
        return chart_left + (i / (len(values) - 1)) * (chart_right - chart_left)

    # Gridlines (4 horizontal bands) with R labels on the right
    steps = 4
    for i in range(steps + 1):
        gv = vmin + span * Decimal(i) / Decimal(steps)
        gy = y_for(gv)
        draw.line([(chart_left, gy), (chart_right, gy)], fill=_GRID, width=1)
        draw.text((chart_right + 10, gy - 8), f"{dec_str(gv.quantize(Decimal('0.1')))}", font=label_font, fill=_GRAY)

    # Zero baseline, emphasized
    zero_y = y_for(Decimal("0"))
    draw.line([(chart_left, zero_y), (chart_right, zero_y)], fill=_GRAY, width=1)

    points = [(x_for(i), y_for(v)) for i, v in enumerate(values)]
    final_positive = values[-1] >= 0
    line_color = _GREEN if final_positive else _RED
    fill_color = _GREEN_DIM if final_positive else _RED_DIM

    # Filled area between the curve and the zero baseline (semi-transparent)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    polygon = [(points[0][0], zero_y)] + points + [(points[-1][0], zero_y)]
    odraw.polygon(polygon, fill=fill_color + (110,))
    base.alpha_composite(overlay) if base.mode == "RGBA" else base.paste(
        Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB"), (0, 0)
    )
    draw = ImageDraw.Draw(base)

    # The line itself, plus small markers if the trade count is manageable
    draw.line(points, fill=line_color, width=4, joint="curve")
    if len(points) <= 40:
        r = 4
        for px, py in points[1:]:
            draw.ellipse([px - r, py - r, px + r, py + r], fill=line_color)


# ---------------------------------------------------------------------------
# Win / loss / breakeven composition bar
# ---------------------------------------------------------------------------

def _draw_composition_bar(draw: ImageDraw.ImageDraw, box, wins: int, losses: int, breakeven: int) -> None:
    x0, y0, x1, y1 = box
    total = max(wins + losses + breakeven, 1)
    bar_h = 22
    bar_y0 = y0 + 34
    bar_y1 = bar_y0 + bar_h

    x = x0
    segments = [(wins, _GREEN), (breakeven, _GRAY), (losses, _RED)]
    for count, color in segments:
        seg_w = (x1 - x0) * (count / total)
        if seg_w > 0:
            draw.rectangle([x, bar_y0, x + seg_w, bar_y1], fill=color)
        x += seg_w

    label_font = _regular(18)
    lx = x0
    def _legend(color, text):
        nonlocal lx
        r = 6
        draw.ellipse([lx, y0 + 6, lx + r * 2, y0 + 6 + r * 2], fill=color)
        lx += r * 2 + 8
        draw.text((lx, y0), text, font=label_font, fill=_WHITE)
        lx += _text_w(draw, text, label_font) + 22

    _legend(_GREEN, f"{wins} Win")
    _legend(_GRAY, f"{breakeven} B/U")
    _legend(_RED, f"{losses} Loss")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def render_report_image(title: str, stats: PeriodStats) -> bytes:
    width = 1000
    padding = 48

    coin_lines = list(stats.coins)[:10]
    extra_count = max(0, len(stats.coins) - len(coin_lines))
    coin_row_h = 42
    coins_h = 70 + len(coin_lines) * coin_row_h + (28 if extra_count else 0)

    header_h = 110
    hero_h = 110
    chart_h = 300
    chips_h = 130
    composition_h = 90
    footer_h = 60

    height = padding * 2 + header_h + hero_h + chart_h + chips_h + composition_h + coins_h + footer_h

    img = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(img)

    y = padding

    # --- Header ---
    draw.text((padding, y), "MEDUZ", font=_bold(40), fill=_ACCENT)
    wordmark_w = _text_w(draw, "MEDUZ ", _bold(40))
    draw.text((padding + wordmark_w, y + 10), "TRADING JOURNAL", font=_regular(20), fill=_GRAY)
    draw.text((padding, y + 48), title, font=_bold(26), fill=_WHITE)
    y += header_h

    # --- Hero total R ---
    total_color = _GREEN if stats.total_r >= 0 else _RED
    total_str = f"{'+' if stats.total_r >= 0 else ''}{dec_str(stats.total_r)}R"
    draw.text((padding, y), total_str, font=_bold(64), fill=total_color)
    subtitle = f"{stats.total_trades} trade · {stats.win_rate}% win rate"
    draw.text((padding, y + 78), subtitle, font=_regular(22), fill=_GRAY)
    y += hero_h

    # --- Equity curve ---
    chart_box = (padding, y, width - padding, y + chart_h)
    _draw_equity_curve(img, chart_box, stats.equity_curve())
    draw = ImageDraw.Draw(img)
    y += chart_h + 24

    # --- Stat chips ---
    pf_str = dec_str(stats.profit_factor) if stats.profit_factor is not None else "∞"
    chip_data = [
        ("Win Rate", f"{stats.win_rate}%"),
        ("Average RR", f"{dec_str(stats.average_rr)}R"),
        ("Profit Factor", pf_str),
        ("Trades", str(stats.total_trades)),
    ]
    chip_gap = 16
    chip_w = (width - padding * 2 - chip_gap * 3) // 4
    for i, (label, value) in enumerate(chip_data):
        x0 = padding + i * (chip_w + chip_gap)
        _rounded_card(draw, [x0, y, x0 + chip_w, y + 100], radius=14)
        draw.text((x0 + 18, y + 18), label, font=_regular(17), fill=_GRAY)
        draw.text((x0 + 18, y + 48), value, font=_bold(28), fill=_WHITE)
    y += chips_h

    # --- Win/loss composition bar ---
    _draw_composition_bar(draw, (padding, y, width - padding, y + composition_h), stats.wins, stats.losses, stats.breakeven)
    y += composition_h

    # --- Coin breakdown ---
    draw.text((padding, y), "COINS", font=_bold(20), fill=_WHITE)
    y += 40
    for i, c in enumerate(coin_lines):
        row_y = y + i * coin_row_h
        if i % 2 == 0:
            draw.rounded_rectangle([padding, row_y, width - padding, row_y + coin_row_h - 6], radius=8, fill=_CARD)
        color = _result_color(c.result_type, c.result_rr)
        draw.ellipse([padding + 14, row_y + 14, padding + 22, row_y + 22], fill=color)
        draw.text((padding + 36, row_y + 9), c.coin, font=_regular(20), fill=_WHITE)
        badge = format_coin_line(c).split("→", 1)[-1].strip()
        badge_w = _text_w(draw, badge, _bold(20))
        draw.text((width - padding - 20 - badge_w, row_y + 9), badge, font=_bold(20), fill=color)
    y += len(coin_lines) * coin_row_h
    if extra_count:
        draw.text((padding, y + 4), f"+ yana {extra_count} ta", font=_regular(18), fill=_GRAY)
        y += 28

    # --- Footer ---
    y += 24
    draw.line([(padding, y), (width - padding, y)], fill=_CARD_BORDER, width=2)
    y += 18
    draw.text((padding, y), "MEDUZ TRADING JOURNAL", font=_regular(18), fill=_GRAY)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
