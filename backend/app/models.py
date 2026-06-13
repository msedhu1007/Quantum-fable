"""Database models — one table per blueprint entity."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WatchlistItem(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class MomentumItem(Base):
    """Tickers tracked on the momentum board — independent of the alert watchlist."""
    __tablename__ = "momentum_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class GrowthValueItem(Base):
    """Tickers tracked on the Growth & Value board — independent of every other list."""
    __tablename__ = "growth_value_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class GrowthValueNote(Base):
    """Human moat thesis per ticker — the qualitative judgment the score can't make.
    Mechanism (why a moat), what would break it, and what to monitor. The score
    triages; the human writes the thesis. Research notes only — not advice."""
    __tablename__ = "growth_value_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)   # why a moat exists
    risks: Mapped[str | None] = mapped_column(Text, nullable=True)    # what breaks it
    watch: Mapped[str | None] = mapped_column(Text, nullable=True)    # what to monitor
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TickerSnapshot(Base):
    __tablename__ = "ticker_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relative_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    dma_20: Mapped[float | None] = mapped_column(Float, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class OptionsSnapshot(Base):
    __tablename__ = "options_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    call_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    put_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    best_call: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    best_put: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), index=True)
    headline: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decision: Mapped[str] = mapped_column(String(12))  # CALL / PUT / NO TRADE
    score: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[str | None] = mapped_column(String(12), nullable=True)
    contract: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risks: Mapped[list | None] = mapped_column(JSON, nullable=True)
    invalidation_level: Mapped[str | None] = mapped_column(String(120), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched: Mapped[bool] = mapped_column(Boolean, default=False)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelDecision(Base):
    __tablename__ = "model_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(12), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
