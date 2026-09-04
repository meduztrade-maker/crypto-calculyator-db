from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    coin: str
    direction: str
    status: str
    risk_percent: Decimal
    entry_price: Decimal
    stop_loss_price: Decimal
    stop_distance_percent: Decimal
    result_type: Optional[str] = None
    result_rr: Optional[Decimal] = None
    opening_screenshot_file_id: Optional[str] = None
    closing_screenshot_file_id: Optional[str] = None
    created_at: datetime
    activated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    missed_at: Optional[datetime] = None

    @field_validator("direction", "status", "result_type", mode="before")
    @classmethod
    def _enum_to_str(cls, v):
        return v.value if hasattr(v, "value") else v


class TradeCreateIn(BaseModel):
    coin: str
    direction: Literal["LONG", "SHORT"]
    risk_percent: Decimal
    entry_price: Decimal
    stop_loss_price: Decimal
    screenshot_file_id: Optional[str] = None


class TradeCloseIn(BaseModel):
    result_type: Literal["SL", "BU", "TP"]
    rr: Optional[Decimal] = None
    screenshot_file_id: Optional[str] = None


class LeverageIn(BaseModel):
    risk: Decimal
    sl_distance_percent: Decimal
    margin: Optional[Decimal] = None


class LeverageOut(BaseModel):
    margin: Decimal
    risk: Decimal
    sl_distance_percent: Decimal
    position_size: Decimal
    leverage: Decimal


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    coin: str
    target_price: Decimal
    direction: str
    price_at_creation: Decimal
    status: str
    created_at: datetime
    triggered_at: Optional[datetime] = None

    @field_validator("direction", "status", mode="before")
    @classmethod
    def _enum_to_str(cls, v):
        return v.value if hasattr(v, "value") else v


class AlertCreateIn(BaseModel):
    coin: str
    target_price: Decimal


class CoinResultOut(BaseModel):
    coin: str
    result_type: str
    result_rr: Optional[Decimal] = None


class StatsOut(BaseModel):
    period_label: str
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: Decimal
    total_r: Decimal
    average_rr: Decimal
    profit_factor: Optional[Decimal] = None
    max_drawdown: Decimal
    streak_kind: str
    streak_count: int
    best_trade: Optional[CoinResultOut] = None
    worst_trade: Optional[CoinResultOut] = None
    coins: list[CoinResultOut]
    equity_curve: list[Decimal]


class MeOut(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    margin: Decimal
    timezone: str
    is_admin: bool


class MarginIn(BaseModel):
    margin: Decimal


class BackupOut(BaseModel):
    backup_type: str
    status: str
    created_at: datetime
