from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.services.stats import compute_period_stats, current_week_bounds, custom_bounds, today_bounds
from webapp.deps import get_current_user, get_session
from webapp.schemas import CoinResultOut, StatsOut

router = APIRouter(prefix="/api/stats", tags=["stats"])

_LABELS = {"daily": "DAILY PERFORMANCE", "weekly": "WEEKLY PERFORMANCE"}


@router.get("", response_model=StatsOut)
async def get_stats(
    period: Literal["daily", "weekly", "custom"] = "daily",
    start: Optional[str] = Query(default=None, description="DD.MM.YYYY, required if period=custom"),
    end: Optional[str] = Query(default=None, description="DD.MM.YYYY, required if period=custom"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if period == "daily":
        bounds = today_bounds()
        label = _LABELS["daily"]
    elif period == "weekly":
        bounds = current_week_bounds()
        label = _LABELS["weekly"]
    else:
        if not start or not end:
            raise HTTPException(status_code=422, detail="start va end kerak (DD.MM.YYYY)")
        try:
            start_dt = datetime.strptime(start, "%d.%m.%Y")
            end_dt = datetime.strptime(end, "%d.%m.%Y")
        except ValueError:
            raise HTTPException(status_code=422, detail="Sana formati: DD.MM.YYYY")
        bounds = custom_bounds(start_dt, end_dt)
        label = f"{start} — {end}"

    stats = await compute_period_stats(session, user, bounds[0], bounds[1])
    streak_kind, streak_count = stats.current_streak()

    return StatsOut(
        period_label=label,
        total_trades=stats.total_trades,
        wins=stats.wins,
        losses=stats.losses,
        breakeven=stats.breakeven,
        win_rate=stats.win_rate,
        total_r=stats.total_r,
        average_rr=stats.average_rr,
        profit_factor=stats.profit_factor,
        max_drawdown=stats.max_drawdown(),
        streak_kind=streak_kind,
        streak_count=streak_count,
        best_trade=CoinResultOut(**vars(stats.best_trade)) if stats.best_trade else None,
        worst_trade=CoinResultOut(**vars(stats.worst_trade)) if stats.worst_trade else None,
        coins=[CoinResultOut(**vars(c)) for c in stats.coins],
        equity_curve=stats.equity_curve(),
    )
