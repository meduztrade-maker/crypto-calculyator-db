from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import TradeStateError, cancel_alert, create_alert, list_active_alerts
from bot.database.models import User
from bot.services.price_feed import PriceLookupError, get_price
from webapp.deps import get_current_user, get_session
from webapp.schemas import AlertCreateIn, AlertOut

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _normalize_symbol(raw: str) -> str:
    coin = raw.strip().upper().replace(" ", "")
    known_quotes = ("USDT", "USDC", "BUSD", "BTC", "ETH", "FDUSD", "TRY", "EUR")
    if not coin.endswith(known_quotes):
        coin += "USDT"
    return coin


@router.get("", response_model=list[AlertOut])
async def get_alerts(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    alerts = await list_active_alerts(session, user)
    return [AlertOut.model_validate(a) for a in alerts]


@router.post("", response_model=AlertOut)
async def create(body: AlertCreateIn, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    coin = _normalize_symbol(body.coin)
    try:
        current = await get_price(coin)
    except PriceLookupError as e:
        raise HTTPException(status_code=422, detail=str(e))
    alert = await create_alert(session, user, coin, body.target_price, current)
    return AlertOut.model_validate(alert)


@router.post("/{alert_id}/cancel")
async def cancel(alert_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    try:
        await cancel_alert(session, user, alert_id)
    except TradeStateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True}


@router.get("/price/{coin}")
async def price(coin: str):
    try:
        p = await get_price(_normalize_symbol(coin))
    except PriceLookupError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"coin": _normalize_symbol(coin), "price": str(p)}
