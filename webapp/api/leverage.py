from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.crud import list_margin_presets
from bot.database.models import User
from bot.services.leverage_calc import calculate_leverage, calculate_leverage_for_presets
from webapp.deps import get_current_user, get_session
from webapp.schemas import LeverageIn, LeverageMultiOut, LeverageResultItem

router = APIRouter(prefix="/api/leverage", tags=["leverage"])


@router.post("", response_model=LeverageMultiOut)
async def leverage(
    body: LeverageIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Returns one leverage result PER saved margin preset at once (spec:
    real + prop accounts computed together, no re-entering margin). If the
    caller passes an explicit `margin`, that's treated as a one-off ad-hoc
    calculation instead. If the user has no presets yet, falls back to
    their legacy single `user.margin` value."""
    try:
        if body.margin is not None:
            result = calculate_leverage(margin=body.margin, risk=body.risk, sl_distance_percent=body.sl_distance_percent)
            results = [
                LeverageResultItem(
                    label="Margin", margin=result.margin, position_size=result.position_size, leverage=result.leverage
                )
            ]
        else:
            presets = await list_margin_presets(session, user)
            pairs = [(p.label, p.amount) for p in presets] if presets else [("Margin", user.margin)]
            computed = calculate_leverage_for_presets(body.risk, body.sl_distance_percent, pairs)
            results = [
                LeverageResultItem(label=label, margin=r.margin, position_size=r.position_size, leverage=r.leverage)
                for label, r in computed
            ]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return LeverageMultiOut(risk=body.risk, sl_distance_percent=body.sl_distance_percent, results=results)
