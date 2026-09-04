from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import (
    TradeStateError,
    activate_trade,
    close_trade_sl,
    close_trade_with_rr,
    create_pending_trade,
    delete_trade,
    force_delete_trade,
    list_active_trades,
    list_pending_trades,
    list_recent_trades,
    miss_trade,
)
from bot.database.models import Direction, ResultType, User
from webapp.deps import get_current_user, get_session
from webapp.schemas import TradeCloseIn, TradeCreateIn, TradeOut

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("/pending", response_model=list[TradeOut])
async def get_pending(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    trades = await list_pending_trades(session, user)
    return [TradeOut.model_validate(t) for t in trades]


@router.get("/active", response_model=list[TradeOut])
async def get_active(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    trades = await list_active_trades(session, user)
    return [TradeOut.model_validate(t) for t in trades]


@router.get("/recent", response_model=list[TradeOut])
async def get_recent(
    limit: int = 5, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    trades = await list_recent_trades(session, user, limit=limit)
    return [TradeOut.model_validate(t) for t in trades]


@router.post("", response_model=TradeOut)
async def create_trade(
    body: TradeCreateIn, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    if body.entry_price <= 0 or body.stop_loss_price <= 0 or body.risk_percent <= 0:
        raise HTTPException(status_code=422, detail="Qiymatlar musbat bo'lishi kerak")
    trade = await create_pending_trade(
        session, user, body.coin, Direction(body.direction), body.risk_percent,
        body.entry_price, body.stop_loss_price, body.screenshot_file_id,
    )
    return TradeOut.model_validate(trade)


@router.post("/{trade_id}/activate", response_model=TradeOut)
async def activate(trade_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    try:
        trade = await activate_trade(session, user, trade_id)
    except TradeStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return TradeOut.model_validate(trade)


@router.post("/{trade_id}/miss", response_model=TradeOut)
async def miss(trade_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    try:
        trade = await miss_trade(session, user, trade_id)
    except TradeStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return TradeOut.model_validate(trade)


@router.delete("/{trade_id}")
async def delete(
    trade_id: int, force: bool = False, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    try:
        if force:
            await force_delete_trade(session, user, trade_id)
        else:
            await delete_trade(session, user, trade_id)
    except TradeStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True}


@router.post("/{trade_id}/close", response_model=TradeOut)
async def close(
    trade_id: int, body: TradeCloseIn, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
):
    try:
        if body.result_type == "SL":
            trade = await close_trade_sl(session, user, trade_id, body.screenshot_file_id)
        else:
            if body.rr is None:
                raise HTTPException(status_code=422, detail="RR qiymati kerak")
            trade = await close_trade_with_rr(
                session, user, trade_id, ResultType(body.result_type), body.rr, body.screenshot_file_id
            )
    except TradeStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return TradeOut.model_validate(trade)
