from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from bot.database.models import User
from bot.services.leverage_calc import calculate_leverage
from webapp.deps import get_current_user
from webapp.schemas import LeverageIn, LeverageMultiOut, LeverageResultItem

router = APIRouter(prefix="/api/leverage", tags=["leverage"])


@router.post("", response_model=LeverageMultiOut)
async def leverage(body: LeverageIn, user: User = Depends(get_current_user)):
    """Each account (a saved margin preset, or a one-off typed-in margin)
    carries ITS OWN risk $ - a $50 account and a $500 account should never
    share one risk amount, since the same dollar risk is a wildly
    different percentage of each. SL distance % is the one input shared
    across accounts, since it comes from the market/setup, not the
    account size."""
    if not body.accounts:
        raise HTTPException(status_code=422, detail="Kamida bitta hisob (marja) kerak")

    results: list[LeverageResultItem] = []
    try:
        for acc in body.accounts:
            r = calculate_leverage(margin=acc.margin, risk=acc.risk, sl_distance_percent=body.sl_distance_percent)
            results.append(
                LeverageResultItem(
                    label=acc.label, margin=r.margin, risk=acc.risk, position_size=r.position_size, leverage=r.leverage
                )
            )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return LeverageMultiOut(sl_distance_percent=body.sl_distance_percent, results=results)
