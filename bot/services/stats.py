from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

import pytz
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import ResultType, Trade, TradeStatus, User
from bot.utils.formatting import dec_str

TZ = pytz.timezone(settings.timezone)


def today_bounds() -> tuple[datetime, datetime]:
    now_local = datetime.now(TZ)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(pytz.utc), end_local.astimezone(pytz.utc)


def current_week_bounds() -> tuple[datetime, datetime]:
    now_local = datetime.now(TZ)
    start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_local = start_of_day - timedelta(days=now_local.weekday())  # Monday
    end_local = start_local + timedelta(days=7)
    return start_local.astimezone(pytz.utc), end_local.astimezone(pytz.utc)


def custom_bounds(start_date: datetime, end_date: datetime) -> tuple[datetime, datetime]:
    start_local = TZ.localize(start_date.replace(hour=0, minute=0, second=0, microsecond=0))
    end_local = TZ.localize(end_date.replace(hour=0, minute=0, second=0, microsecond=0)) + timedelta(days=1)
    return start_local.astimezone(pytz.utc), end_local.astimezone(pytz.utc)


@dataclass
class CoinResult:
    coin: str
    result_type: str
    result_rr: Decimal | None


@dataclass
class PeriodStats:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    win_rate: Decimal = Decimal("0")
    total_r: Decimal = Decimal("0")
    average_rr: Decimal = Decimal("0")
    profit_factor: Decimal | None = None  # None means "no losses" (undefined / infinite)
    best_trade: CoinResult | None = None
    worst_trade: CoinResult | None = None
    coins: list[CoinResult] = field(default_factory=list)

    def equity_curve(self) -> list[Decimal]:
        """Cumulative R in chronological order (self.coins is newest-first, so reverse it)."""
        cumulative: list[Decimal] = []
        running = Decimal("0")
        for c in reversed(self.coins):
            running += c.result_rr or Decimal("0")
            cumulative.append(running)
        return cumulative


async def compute_period_stats(session: AsyncSession, user: User, start: datetime, end: datetime) -> PeriodStats:
    base_filter = (
        Trade.user_id == user.id,
        Trade.status == TradeStatus.CLOSED,
        Trade.closed_at >= start,
        Trade.closed_at < end,
    )

    # Win/Loss/BE classification per spec section 31:
    #   TP or BU with positive RR -> win; SL -> loss; RR == 0 -> breakeven; missed excluded (already, via status filter)
    win_case = case((Trade.result_rr > 0, 1), else_=0)
    loss_case = case((Trade.result_type == ResultType.SL, 1), else_=0)
    be_case = case((Trade.result_rr == 0, 1), else_=0)

    agg_stmt = select(
        func.count(Trade.id),
        func.coalesce(func.sum(win_case), 0),
        func.coalesce(func.sum(loss_case), 0),
        func.coalesce(func.sum(be_case), 0),
        func.coalesce(func.sum(Trade.result_rr), Decimal("0")),
    ).where(*base_filter)

    result = await session.execute(agg_stmt)
    total, wins, losses, breakeven, total_r = result.one()

    stats = PeriodStats(
        total_trades=total,
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        total_r=total_r or Decimal("0"),
    )

    if total > 0:
        stats.average_rr = (stats.total_r / total).quantize(Decimal("0.01"))
    denom = wins + losses
    if denom > 0:
        stats.win_rate = (Decimal(wins) / Decimal(denom) * Decimal("100")).quantize(Decimal("0.1"))

    # Best / worst trade
    best_stmt = (
        select(Trade.coin, Trade.result_type, Trade.result_rr)
        .where(*base_filter)
        .order_by(Trade.result_rr.desc())
        .limit(1)
    )
    worst_stmt = (
        select(Trade.coin, Trade.result_type, Trade.result_rr)
        .where(*base_filter)
        .order_by(Trade.result_rr.asc())
        .limit(1)
    )
    best_row = (await session.execute(best_stmt)).first()
    worst_row = (await session.execute(worst_stmt)).first()
    if best_row:
        stats.best_trade = CoinResult(best_row[0], best_row[1].value if best_row[1] else "-", best_row[2])
    if worst_row:
        stats.worst_trade = CoinResult(worst_row[0], worst_row[1].value if worst_row[1] else "-", worst_row[2])

    # Per-coin breakdown, most recent first
    coins_stmt = (
        select(Trade.coin, Trade.result_type, Trade.result_rr)
        .where(*base_filter)
        .order_by(Trade.closed_at.desc())
    )
    coins_rows = (await session.execute(coins_stmt)).all()
    stats.coins = [CoinResult(r[0], r[1].value if r[1] else "-", r[2]) for r in coins_rows]

    sum_pos = sum((c.result_rr for c in stats.coins if c.result_rr and c.result_rr > 0), Decimal("0"))
    sum_neg_abs = sum((abs(c.result_rr) for c in stats.coins if c.result_rr and c.result_rr < 0), Decimal("0"))
    if sum_neg_abs > 0:
        stats.profit_factor = (sum_pos / sum_neg_abs).quantize(Decimal("0.01"))

    return stats


def format_coin_line(c: CoinResult) -> str:
    if c.result_type == "SL":
        return f"{c.coin} → SL"
    if c.result_type == "BU":
        sign = "+" if (c.result_rr or 0) >= 0 else ""
        return f"{c.coin} → B/U {sign}{dec_str(c.result_rr) if c.result_rr is not None else 0}R"
    sign = "+" if (c.result_rr or 0) >= 0 else ""
    return f"{c.coin} → {sign}{dec_str(c.result_rr) if c.result_rr is not None else 0}R"


def format_text_report(title: str, stats: PeriodStats) -> str:
    lines = [
        "MEDUZ JOURNAL",
        "",
        title,
        "",
        f"Trades: {stats.total_trades}",
        f"Wins: {stats.wins}",
        f"Losses: {stats.losses}",
        f"B/U: {stats.breakeven}",
        "",
        f"Win Rate: {stats.win_rate}%",
        "",
        f"Total: {'+' if stats.total_r >= 0 else ''}{dec_str(stats.total_r)}R",
        "",
        f"Average RR: {dec_str(stats.average_rr)}R",
        f"Profit Factor: {dec_str(stats.profit_factor) if stats.profit_factor is not None else '∞'}",
    ]
    if stats.coins:
        lines.append("")
        lines.append("COINS")
        lines.append("")
        lines.extend(format_coin_line(c) for c in stats.coins)
    if stats.best_trade:
        lines.append("")
        lines.append(f"🏆 Eng yaxshi: {format_coin_line(stats.best_trade)}")
    if stats.worst_trade and stats.total_trades > 1:
        lines.append(f"📉 Eng yomon: {format_coin_line(stats.worst_trade)}")
    return "\n".join(lines)
