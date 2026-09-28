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


def calculate_leverage_for_accounts(
    accounts: list[tuple[str, Decimal, Decimal]], sl_distance_percent: Decimal
) -> list[tuple[str, LeverageResult]]:
    """accounts: (label, margin, risk) triples. Each account gets its OWN
    risk $ - a $50 account and a $500 account should never share one
    risk amount, since the same dollar figure is a wildly different
    percentage of each. SL distance is the one thing shared across
    accounts, since it comes from the market setup, not account size."""
    return [
        (label, calculate_leverage(margin=margin, risk=risk, sl_distance_percent=sl_distance_percent))
        for label, margin, risk in accounts
    ]


def format_leverage_results_multi(sl_distance_percent: Decimal, results: list[tuple[str, LeverageResult]]) -> str:
    lines = ["🧮 LEVERAGE CALCULATOR", "", f"SL Distance: {dec_str(sl_distance_percent)}%", ""]
    for label, r in results:
        lines.append(
            f"• {label}: margin ${dec_str(r.margin)}, risk ${dec_str(r.risk)} "
            f"→ {dec_str(r.leverage)}X (position: ${dec_str(r.position_size)})"
        )
    return "\n".join(lines)
