from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Direction(str, enum.Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"


class ResultType(str, enum.Enum):
    SL = "SL"
    BU = "BU"
    TP = "TP"


class BackupType(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    MANUAL = "MANUAL"


class BackupStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    margin: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("500"))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Tashkent")
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    trades: Mapped[list["Trade"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    coin: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[Direction] = mapped_column(Enum(Direction, name="direction_enum"), nullable=False)
    status: Mapped[TradeStatus] = mapped_column(
        Enum(TradeStatus, name="trade_status_enum"), default=TradeStatus.PENDING, index=True
    )

    risk_percent: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    stop_loss_price: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    stop_distance_percent: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    result_type: Mapped[ResultType | None] = mapped_column(Enum(ResultType, name="result_type_enum"), nullable=True)
    result_rr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    opening_screenshot_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    closing_screenshot_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    missed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="trades")


class Backup(Base):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(primary_key=True)
    backup_type: Mapped[BackupType] = mapped_column(Enum(BackupType, name="backup_type_enum"), nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    file_name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[BackupStatus] = mapped_column(Enum(BackupStatus, name="backup_status_enum"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
