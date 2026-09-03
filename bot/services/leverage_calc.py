from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from bot.utils.formatting import dec_str


@dataclass
class LeverageResult:
    margin: Decimal
    risk: Decimal
    sl_distance_percent: Decimal
    position_size: Decimal
    leverage: Decimal


def calculate_leverage(margin: Decimal, risk: Decimal, sl_distance_percent: Decimal) -> LeverageResult:
    """
    Risk = Position Size x SL%
    Position Size = Risk / SL%
    Leverage = Position Size / Margin
    """
    if margin <= 0:
        raise ValueError("Margin must be positive")
    if sl_distance_percent <= 0:
        raise ValueError("SL distance must be positive")

    sl_fraction = sl_distance_percent / Decimal("100")
    position_size = (risk / sl_fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    leverage = (position_size / margin).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return LeverageResult(
        margin=margin,
        risk=risk,
        sl_distance_percent=sl_distance_percent,
        position_size=position_size,
        leverage=leverage,
    )


def format_leverage_result(r: LeverageResult) -> str:
    return (
        "🧮 LEVERAGE CALCULATOR\n\n"
        f"Margin: ${dec_str(r.margin)}\n\n"
        f"Risk: ${dec_str(r.risk)}\n\n"
        f"SL Distance: {dec_str(r.sl_distance_percent)}%\n\n"
        f"Required Leverage: {dec_str(r.leverage)}X\n\n"
        "Formula:\n"
        "Risk = Position Size × SL%\n"
        "Position Size = Risk / SL%\n"
        "Leverage = Position Size / Margin"
    )
