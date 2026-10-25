import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TradingSettings(Base):
    __tablename__ = "trading_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    live_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_stake: Mapped[float] = mapped_column(Float, default=1.0)
    daily_loss_cap: Mapped[float] = mapped_column(Float, default=10.0)
    max_trades_per_hour: Mapped[int] = mapped_column(Integer, default=60)
    max_consecutive_losses: Mapped[int] = mapped_column(Integer, default=8)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deriv_accounts.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    mode: Mapped[str] = mapped_column(String(10))
    strategy: Mapped[str] = mapped_column(String(40))
    symbol: Mapped[str] = mapped_column(String(40))
    contract_type: Mapped[str] = mapped_column(String(20))
    barrier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    duration: Mapped[int] = mapped_column(Integer)
    step: Mapped[int] = mapped_column(Integer, default=1)
    stake: Mapped[float] = mapped_column(Float)
    payout: Mapped[float | None] = mapped_column(Float, nullable=True)
    fair_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    contract_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="open")
    profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    signal_epoch: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    entry_epoch: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)