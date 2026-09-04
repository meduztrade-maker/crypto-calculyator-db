from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from bot.database.models import User
from bot.services.leverage_calc import calculate_leverage
from webapp.deps import get_current_user
from webapp.schemas import LeverageIn, LeverageOut

router = APIRouter(prefix="/api/leverage", tags=["leverage"])


@router.post("", response_model=LeverageOut)
async def leverage(body: LeverageIn, user: User = Depends(get_current_user)):
    margin = body.margin if body.margin is not None else user.margin
    try:
        result = calculate_leverage(margin=margin, risk=body.risk, sl_distance_percent=body.sl_distance_percent)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return LeverageOut(
        margin=result.margin, risk=result.risk, sl_distance_percent=result.sl_distance_percent,
        position_size=result.position_size, leverage=result.leverage,
    )
