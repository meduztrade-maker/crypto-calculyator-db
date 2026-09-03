from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import Alert, AlertDirection, AlertStatus, Direction, ResultType, Trade, TradeStatus, User


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str | None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        if username and user.username != username:
            user.username = username
            await session.commit()
        return user

    user = User(
        telegram_id=telegram_id,
        username=username,
        margin=Decimal(settings.default_margin),
        timezone=settings.timezone,
        is_admin=(telegram_id == settings.admin_id),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_margin(session: AsyncSession, user: User, margin: Decimal) -> User:
    user.margin = margin
    await session.commit()
    await session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Trades — creation
# ---------------------------------------------------------------------------

def compute_stop_distance_percent(entry: Decimal, sl: Decimal) -> Decimal:
    if entry == 0:
        raise ValueError("Entry price cannot be zero")
    distance = abs(entry - sl) / entry * Decimal("100")
    return distance.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


async def create_pending_trade(
    session: AsyncSession,
    user: User,
    coin: str,
    direction: Direction,
    risk_percent: Decimal,
    entry_price: Decimal,
    stop_loss_price: Decimal,
    opening_screenshot_file_id: str,
) -> Trade:
    trade = Trade(
        user_id=user.id,
        coin=coin.upper(),
        direction=direction,
        status=TradeStatus.PENDING,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        stop_distance_percent=compute_stop_distance_percent(entry_price, stop_loss_price),
        opening_screenshot_file_id=opening_screenshot_file_id,
    )
    session.add(trade)
    await session.commit()
    await session.refresh(trade)
    return trade


# ---------------------------------------------------------------------------
# Trades — lookups (always scoped by user_id, spec section 26: user isolation)
# ---------------------------------------------------------------------------

async def get_user_trade(session: AsyncSession, user: User, trade_id: int, *, lock: bool = False) -> Trade | None:
    stmt = select(Trade).where(Trade.id == trade_id, Trade.user_id == user.id)
    if lock:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_pending_trades(session: AsyncSession, user: User) -> list[Trade]:
    result = await session.execute(
        select(Trade)
        .where(Trade.user_id == user.id, Trade.status == TradeStatus.PENDING)
        .order_by(Trade.created_at.desc())
    )
    return list(result.scalars().all())


async def list_active_trades(session: AsyncSession, user: User) -> list[Trade]:
    result = await session.execute(
        select(Trade)
        .where(Trade.user_id == user.id, Trade.status == TradeStatus.ACTIVE)
        .order_by(Trade.activated_at.desc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Trades — state transitions
# ---------------------------------------------------------------------------

class TradeStateError(Exception):
    """Raised when a trade is not in the expected state (e.g. double-click race)."""


async def activate_trade(session: AsyncSession, user: User, trade_id: int) -> Trade:
    trade = await get_user_trade(session, user, trade_id, lock=True)
    if trade is None or trade.status != TradeStatus.PENDING:
        raise TradeStateError("Trade is not pending")
    trade.status = TradeStatus.ACTIVE
    trade.activated_at = _now()
    await session.commit()
    await session.refresh(trade)
    return trade


async def miss_trade(session: AsyncSession, user: User, trade_id: int) -> Trade:
    trade = await get_user_trade(session, user, trade_id, lock=True)
    if trade is None or trade.status != TradeStatus.PENDING:
        raise TradeStateError("Trade is not pending")
    trade.status = TradeStatus.MISSED
    trade.missed_at = _now()
    await session.commit()
    await session.refresh(trade)
    return trade


async def delete_trade(session: AsyncSession, user: User, trade_id: int) -> None:
    trade = await get_user_trade(session, user, trade_id, lock=True)
    if trade is None or trade.status not in (TradeStatus.PENDING,):
        raise TradeStateError("Only pending trades can be deleted")
    await session.delete(trade)
    await session.commit()


async def list_recent_trades(session: AsyncSession, user: User, limit: int = 5) -> list[Trade]:
    """Last N trades regardless of status — for the '🗑 Oxirgi tradelar' cleanup screen."""
    result = await session.execute(
        select(Trade)
        .where(Trade.user_id == user.id)
        .order_by(Trade.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def force_delete_trade(session: AsyncSession, user: User, trade_id: int) -> None:
    """Deletes a trade regardless of its status (used from the recent-trades cleanup screen)."""
    trade = await get_user_trade(session, user, trade_id, lock=True)
    if trade is None:
        raise TradeStateError("Trade not found")
    await session.delete(trade)
    await session.commit()


async def close_trade_sl(session: AsyncSession, user: User, trade_id: int, closing_screenshot_file_id: str) -> Trade:
    trade = await get_user_trade(session, user, trade_id, lock=True)
    if trade is None or trade.status != TradeStatus.ACTIVE:
        raise TradeStateError("Trade is not active")
    trade.status = TradeStatus.CLOSED
    trade.result_type = ResultType.SL
    trade.result_rr = Decimal("-1")
    trade.closing_screenshot_file_id = closing_screenshot_file_id
    trade.closed_at = _now()
    await session.commit()
    await session.refresh(trade)
    return trade


async def close_trade_with_rr(
    session: AsyncSession,
    user: User,
    trade_id: int,
    result_type: ResultType,
    rr: Decimal,
    closing_screenshot_file_id: str,
) -> Trade:
    if result_type not in (ResultType.BU, ResultType.TP):
        raise ValueError("result_type must be BU or TP for this transition")
    trade = await get_user_trade(session, user, trade_id, lock=True)
    if trade is None or trade.status != TradeStatus.ACTIVE:
        raise TradeStateError("Trade is not active")
    trade.status = TradeStatus.CLOSED
    trade.result_type = result_type
    trade.result_rr = rr
    trade.closing_screenshot_file_id = closing_screenshot_file_id
    trade.closed_at = _now()
    await session.commit()
    await session.refresh(trade)
    return trade


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

async def create_alert(
    session: AsyncSession, user: User, coin: str, target_price: Decimal, current_price: Decimal
) -> Alert:
    direction = AlertDirection.ABOVE if target_price >= current_price else AlertDirection.BELOW
    alert = Alert(
        user_id=user.id,
        coin=coin.upper(),
        target_price=target_price,
        direction=direction,
        price_at_creation=current_price,
        status=AlertStatus.ACTIVE,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


async def list_active_alerts(session: AsyncSession, user: User) -> list[Alert]:
    result = await session.execute(
        select(Alert)
        .where(Alert.user_id == user.id, Alert.status == AlertStatus.ACTIVE)
        .order_by(Alert.created_at.desc())
    )
    return list(result.scalars().all())


async def cancel_alert(session: AsyncSession, user: User, alert_id: int) -> Alert:
    result = await session.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id).with_for_update()
    )
    alert = result.scalar_one_or_none()
    if alert is None or alert.status != AlertStatus.ACTIVE:
        raise TradeStateError("Alert is not active")
    alert.status = AlertStatus.CANCELLED
    await session.commit()
    await session.refresh(alert)
    return alert


async def list_all_active_alerts(session: AsyncSession) -> list[Alert]:
    result = await session.execute(select(Alert).where(Alert.status == AlertStatus.ACTIVE))
    return list(result.scalars().all())


async def mark_alert_triggered(session: AsyncSession, alert_id: int) -> Alert | None:
    result = await session.execute(select(Alert).where(Alert.id == alert_id).with_for_update())
    alert = result.scalar_one_or_none()
    if alert is None or alert.status != AlertStatus.ACTIVE:
        return None
    alert.status = AlertStatus.TRIGGERED
    alert.triggered_at = _now()
    await session.commit()
    await session.refresh(alert)
    return alert
