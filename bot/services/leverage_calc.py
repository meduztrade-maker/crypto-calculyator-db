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


def calculate_leverage_for_presets(
    risk: Decimal, sl_distance_percent: Decimal, presets: list[tuple[str, Decimal]]
) -> list[tuple[str, LeverageResult]]:
    """One LeverageResult per (label, margin) preset, same risk/SL for
    all of them - so switching between e.g. a real account and a prop
    account no longer means re-entering margin and recalculating twice."""
    return [(label, calculate_leverage(margin=margin, risk=risk, sl_distance_percent=sl_distance_percent))
            for label, margin in presets]


def format_leverage_results_multi(risk: Decimal, sl_distance_percent: Decimal, results: list[tuple[str, LeverageResult]]) -> str:
    lines = [
        "🧮 LEVERAGE CALCULATOR",
        "",
        f"Risk: ${dec_str(risk)}",
        f"SL Distance: {dec_str(sl_distance_percent)}%",
        "",
    ]
    for label, r in results:
        lines.append(f"• {label} (${dec_str(r.margin)}) → {dec_str(r.leverage)}X (position: ${dec_str(r.position_size)})")
    return "\n".join(lines)
