from __future__ import annotations

import io
import os
from decimal import Decimal

from PIL import Image, ImageDraw, ImageFont

from bot.services.stats import PeriodStats, format_coin_line
from bot.utils.formatting import dec_str

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "fonts")

_BG_TOP = (14, 18, 26)
_BG_BOTTOM = (9, 12, 17)
_CARD = (20, 25, 33)
_CARD_ALT = (17, 21, 28)
_CARD_BORDER = (34, 41, 52)
_GRID = (33, 40, 50)
_GREEN = (46, 204, 113)
_GREEN_DIM = (28, 82, 55)
_RED = (239, 68, 68)
_RED_DIM = (86, 34, 34)
_GRAY = (139, 148, 158)
_GRAY_DIM = (72, 79, 90)
_WHITE = (237, 242, 247)
_ACCENT = (88, 166, 255)
_ACCENT_DIM = (30, 52, 84)
_GOLD = (240, 180, 60)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(_ASSETS_DIR, name), size)


def _bold(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSans-Bold.ttf", size)


def _regular(size: int) -> ImageFont.FreeTypeFont:
    return _font("DejaVuSans.ttf", size)


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=font)


def _vertical_gradient(size, top, bottom) -> Image.Image:
    w, h = size
    grad = Image.new("RGB", (1, h))
    gdraw = ImageDraw.Draw(grad)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        gdraw.point((0, y), fill=(r, g, b))
    return grad.resize((w, h))


def _card(draw: ImageDraw.ImageDraw, box, radius=18, fill=_CARD, outline=_CARD_BORDER, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _result_color(result_type: str, rr) -> tuple:
    if result_type == "SL":
        return _RED
    if rr is not None and rr > 0:
        return _GREEN
    return _GRAY


def _alpha_fill_polygon(base: Image.Image, polygon, color_rgb, alpha) -> None:
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).polygon(polygon, fill=color_rgb + (alpha,))
    composited = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    base.paste(composited, (0, 0))


# ---------------------------------------------------------------------------
# Main chart card: equity curve (top) + per-trade R bars (bottom), sharing
# one x-axis — the classic dual-panel layout used by trading platforms.
# ---------------------------------------------------------------------------

def _draw_main_chart(base: Image.Image, box, stats: PeriodStats) -> None:
    x0, y0, x1, y1 = box
    draw = ImageDraw.Draw(base)
    _card(draw, box, radius=20)

    title_font = _bold(21)
    label_font = _regular(17)
    small_font = _regular(15)

    draw.text((x0 + 26, y0 + 20), "EQUITY CURVE", font=title_font, fill=_WHITE)

    curve = stats.equity_curve()
    trades = stats.chronological_trades()

    if not curve:
        draw.text(
            ((x0 + x1) // 2 - 90, (y0 + y1) // 2 - 10),
            "Yopilgan trade yo'q", font=_regular(20), fill=_GRAY,
        )
        return

    max_dd = stats.max_drawdown()
    if max_dd > 0:
        dd_text = f"Max Drawdown: -{dec_str(max_dd)}R"
        dd_w = _text_w(draw, dd_text, small_font)
        draw.text((x1 - 26 - dd_w, y0 + 26), dd_text, font=small_font, fill=_RED)

    divider_y = y0 + int((y1 - y0) * 0.66)
    equity_top, equity_bottom = y0 + 60, divider_y - 16
    bars_top, bars_bottom = divider_y + 22, y1 - 34
    chart_left, chart_right = x0 + 26, x1 - 74

    values = [Decimal("0")] + curve
    vmax, vmin = max(values), min(values)
    if vmax == vmin:
        vmax += Decimal("1")
        vmin -= Decimal("1")
    span = vmax - vmin
    pad = span * Decimal("0.18") or Decimal("1")
    vmax, vmin = vmax + pad, vmin - pad
    span = vmax - vmin

    def eq_y(v: Decimal) -> float:
        return equity_bottom - float((v - vmin) / span) * (equity_bottom - equity_top)

    def x_for(i: int, n: int) -> float:
        if n <= 1:
            return chart_left
        return chart_left + (i / (n - 1)) * (chart_right - chart_left)

    steps = 3
    for i in range(steps + 1):
        gv = vmin + span * Decimal(i) / Decimal(steps)
        gy = eq_y(gv)
        draw.line([(chart_left, gy), (chart_right, gy)], fill=_GRID, width=1)
        draw.text((chart_right + 10, gy - 8), dec_str(gv.quantize(Decimal("0.1"))), font=small_font, fill=_GRAY)

    zero_y = eq_y(Decimal("0"))
    draw.line([(chart_left, zero_y), (chart_right, zero_y)], fill=_GRAY_DIM, width=1)

    points = [(x_for(i, len(values)), eq_y(v)) for i, v in enumerate(values)]
    final_positive = values[-1] >= 0
    line_color = _GREEN if final_positive else _RED
    fill_color = _GREEN_DIM if final_positive else _RED_DIM

    polygon = [(points[0][0], zero_y)] + points + [(points[-1][0], zero_y)]
    _alpha_fill_polygon(base, polygon, fill_color, 130)
    draw = ImageDraw.Draw(base)

    # mark the drawdown trough, if any
    if max_dd > 0:
        running_peak = Decimal("0")
        trough_idx, trough_val, worst_dd = 0, Decimal("0"), Decimal("-1")
        for i, v in enumerate(values):
            if v > running_peak:
                running_peak = v
            dd = running_peak - v
            if dd > worst_dd:
                worst_dd, trough_idx, trough_val = dd, i, v
        tx, ty = x_for(trough_idx, len(values)), eq_y(trough_val)
        draw.line([(tx, ty), (tx, equity_bottom)], fill=_RED, width=1)

    draw.line(points, fill=line_color, width=4, joint="curve")
    if len(points) <= 40:
        r = 4
        for px, py in points[1:]:
            draw.ellipse([px - r, py - r, px + r, py + r], fill=line_color)

    # --- Divider + per-trade R bar sub-panel ---
    draw.line([(x0 + 26, divider_y), (x1 - 26, divider_y)], fill=_CARD_BORDER, width=1)
    draw.text((x0 + 26, divider_y + 2), "PER-TRADE R", font=_regular(15), fill=_GRAY)

    bar_max = max((abs(t.result_rr or Decimal("0")) for t in trades), default=Decimal("1")) or Decimal("1")
    bars_mid = (bars_top + bars_bottom) // 2
    half_h = (bars_bottom - bars_top) // 2 - 4
    n = len(trades)
    slot_w = (chart_right - chart_left) / max(n, 1)
    bar_w = max(min(slot_w * 0.55, 28), 3)

    for i, t in enumerate(trades):
        cx = chart_left + slot_w * (i + 0.5) if n > 1 else (chart_left + chart_right) / 2
        rr = t.result_rr or Decimal("0")
        color = _result_color(t.result_type, rr)
        if rr == 0:
            draw.line([(cx - bar_w / 2, bars_mid), (cx + bar_w / 2, bars_mid)], fill=_GRAY, width=3)
            continue
        frac = min(abs(float(rr)) / float(bar_max), 1.0)
        h = frac * half_h
        if rr > 0:
            draw.rounded_rectangle([cx - bar_w / 2, bars_mid - h, cx + bar_w / 2, bars_mid], radius=3, fill=color)
        else:
            draw.rounded_rectangle([cx - bar_w / 2, bars_mid, cx + bar_w / 2, bars_mid + h], radius=3, fill=color)

    draw.line([(chart_left, bars_mid), (chart_right, bars_mid)], fill=_GRAY_DIM, width=1)


def _draw_composition_bar(draw: ImageDraw.ImageDraw, box, wins: int, losses: int, breakeven: int) -> None:
    x0, y0, x1, y1 = box
    total = max(wins + losses + breakeven, 1)
    bar_h = 22
    bar_y0 = y0 + 34
    bar_y1 = bar_y0 + bar_h

    x = x0
    for count, color in ((wins, _GREEN), (breakeven, _GRAY), (losses, _RED)):
        seg_w = (x1 - x0) * (count / total)
        if seg_w > 0:
            draw.rectangle([x, bar_y0, x + seg_w, bar_y1], fill=color)
        x += seg_w

    label_font = _regular(18)
    lx = x0

    def legend(color, text):
        nonlocal lx
        r = 6
        draw.ellipse([lx, y0 + 6, lx + r * 2, y0 + 6 + r * 2], fill=color)
        lx += r * 2 + 8
        draw.text((lx, y0), text, font=label_font, fill=_WHITE)
        lx += _text_w(draw, text, label_font) + 24

    legend(_GREEN, f"{wins} Win")
    legend(_GRAY, f"{breakeven} B/U")
    legend(_RED, f"{losses} Loss")


def _streak_badge(draw: ImageDraw.ImageDraw, xy, kind: str, count: int) -> None:
    x, y = xy
    if kind in ("none",) or count == 0:
        return
    if kind == "win":
        text, color, bg = f"{count} g'alaba ketma-ket", _GREEN, _GREEN_DIM
    elif kind == "loss":
        text, color, bg = f"{count} zarar ketma-ket", _RED, _RED_DIM
    else:
        text, color, bg = "B/U", _GRAY, _CARD_ALT
    font = _regular(18)
    tw = _text_w(draw, text, font)
    pad_l, pad_r = 34, 16
    h = 40
    draw.rounded_rectangle([x, y, x + tw + pad_l + pad_r, y + h], radius=20, fill=bg)
    # small triangular indicator instead of an emoji glyph (not all fonts render emoji)
    cx, cy = x + 18, y + h // 2
    if kind == "win":
        draw.polygon([(cx - 6, cy + 5), (cx + 6, cy + 5), (cx, cy - 7)], fill=color)  # up triangle
    elif kind == "loss":
        draw.polygon([(cx - 6, cy - 5), (cx + 6, cy - 5), (cx, cy + 7)], fill=color)  # down triangle
    else:
        draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=color)
    draw.text((x + pad_l, y + 9), text, font=font, fill=color)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def render_report_image(title: str, stats: PeriodStats) -> bytes:
    width = 1000
    padding = 44

    coin_lines = list(stats.coins)[:10]
    extra_count = max(0, len(stats.coins) - len(coin_lines))
    coin_row_h = 44
    coins_h = 66 + len(coin_lines) * coin_row_h + (30 if extra_count else 0)

    header_h = 96
    hero_h = 118
    chart_h = 380
    chips_h = 2 * 96 + 16
    composition_h = 90
    footer_h = 56

    height = padding * 2 + header_h + hero_h + chart_h + 26 + chips_h + 22 + composition_h + coins_h + footer_h

    img = _vertical_gradient((width, height), _BG_TOP, _BG_BOTTOM)
    draw = ImageDraw.Draw(img)

    y = padding

    # --- Header ---
    draw.text((padding, y), "MEDUZ", font=_bold(40), fill=_ACCENT)
    wordmark_w = _text_w(draw, "MEDUZ ", _bold(40))
    draw.text((padding + wordmark_w, y + 10), "TRADING JOURNAL", font=_regular(19), fill=_GRAY)
    draw.text((padding, y + 50), title, font=_bold(25), fill=_WHITE)
    draw.line([(padding, y + header_h - 8), (width - padding, y + header_h - 8)], fill=_ACCENT_DIM, width=2)
    y += header_h

    # --- Hero total R + streak badge ---
    total_color = _GREEN if stats.total_r >= 0 else _RED
    total_str = f"{'+' if stats.total_r >= 0 else ''}{dec_str(stats.total_r)}R"
    draw.text((padding, y), total_str, font=_bold(66), fill=total_color)
    hero_w = _text_w(draw, total_str, _bold(66))

    streak_kind, streak_count = stats.current_streak()
    _streak_badge(draw, (padding + hero_w + 28, y + 14), streak_kind, streak_count)

    subtitle = f"{stats.total_trades} trade · {stats.win_rate}% win rate"
    draw.text((padding, y + 82), subtitle, font=_regular(21), fill=_GRAY)
    y += hero_h

    # --- Main dual-panel chart ---
    _draw_main_chart(img, (padding, y, width - padding, y + chart_h), stats)
    draw = ImageDraw.Draw(img)
    y += chart_h + 26

    # --- Stat chips: 3 columns x 2 rows ---
    pf_str = dec_str(stats.profit_factor) if stats.profit_factor is not None else "∞"
    best_str = format_coin_line(stats.best_trade).split("→", 1)[-1].strip() if stats.best_trade else "-"
    worst_str = format_coin_line(stats.worst_trade).split("→", 1)[-1].strip() if stats.worst_trade else "-"
    dd = stats.max_drawdown()
    chips_row1 = [("Win Rate", f"{stats.win_rate}%"), ("Average RR", f"{dec_str(stats.average_rr)}R"), ("Profit Factor", pf_str)]
    chips_row2 = [("Max Drawdown", f"-{dec_str(dd)}R" if dd > 0 else "0R"), ("Eng yaxshi", best_str), ("Trades", str(stats.total_trades))]

    chip_gap = 16
    chip_w = (width - padding * 2 - chip_gap * 2) // 3
    for row_i, row in enumerate([chips_row1, chips_row2]):
        for i, (label, value) in enumerate(row):
            x0 = padding + i * (chip_w + chip_gap)
            cy = y + row_i * (96 + 16)
            _card(draw, [x0, cy, x0 + chip_w, cy + 96], radius=14)
            draw.text((x0 + 18, cy + 16), label, font=_regular(16), fill=_GRAY)
            vcolor = _WHITE
            if label == "Max Drawdown" and dd > 0:
                vcolor = _RED
            elif label == "Eng yaxshi" and stats.best_trade is not None:
                vcolor = _GREEN
            vfont = _bold(24) if len(value) > 8 else _bold(27)
            draw.text((x0 + 18, cy + 46), value, font=vfont, fill=vcolor)
    y += chips_h

    # --- Win/loss composition ---
    y += 22
    _draw_composition_bar(draw, (padding, y, width - padding, y + composition_h), stats.wins, stats.losses, stats.breakeven)
    y += composition_h

    # --- Coin breakdown, with a magnitude bar behind each badge ---
    draw.text((padding, y), "COINS", font=_bold(20), fill=_WHITE)
    y += 38
    max_abs = max((abs(c.result_rr) for c in coin_lines if c.result_rr), default=Decimal("1")) or Decimal("1")
    for i, c in enumerate(coin_lines):
        row_y = y + i * coin_row_h
        row_h = coin_row_h - 6
        if i % 2 == 0:
            draw.rounded_rectangle([padding, row_y, width - padding, row_y + row_h], radius=8, fill=_CARD_ALT)
        color = _result_color(c.result_type, c.result_rr)

        if c.result_rr:
            frac = min(abs(float(c.result_rr)) / float(max_abs), 1.0)
            bar_full_w = width - padding * 2 - 40
            mag_w = frac * bar_full_w
            mag_color = _GREEN_DIM if color == _GREEN else (_RED_DIM if color == _RED else _CARD_ALT)
            draw.rounded_rectangle([padding + 30, row_y + 4, padding + 30 + mag_w, row_y + row_h - 4], radius=6, fill=mag_color)

        draw.ellipse([padding + 14, row_y + row_h // 2 - 5, padding + 24, row_y + row_h // 2 + 5], fill=color)
        draw.text((padding + 36, row_y + 8), c.coin, font=_regular(20), fill=_WHITE)
        badge = format_coin_line(c).split("→", 1)[-1].strip()
        badge_w = _text_w(draw, badge, _bold(20))
        draw.text((width - padding - 20 - badge_w, row_y + 8), badge, font=_bold(20), fill=color)
    y += len(coin_lines) * coin_row_h
    if extra_count:
        draw.text((padding, y + 4), f"+ yana {extra_count} ta", font=_regular(18), fill=_GRAY)
        y += 30

    # --- Footer ---
    y += 20
    draw.line([(padding, y), (width - padding, y)], fill=_CARD_BORDER, width=2)
    y += 18
    draw.text((padding, y), "MEDUZ TRADING JOURNAL", font=_regular(18), fill=_GRAY)
    ts = "generated by @Tradejournal1bot"
    ts_w = _text_w(draw, ts, _regular(15))
    draw.text((width - padding - ts_w, y + 3), ts, font=_regular(15), fill=_GRAY_DIM)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
