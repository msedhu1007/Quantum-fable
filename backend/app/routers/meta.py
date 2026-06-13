"""Provider status, effective scanner settings, and momentum rankings."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import momentum
from ..config import get_settings
from ..db import get_db
from ..models import MomentumItem
from ..providers.alphavantage import alphavantage
from ..providers.benzinga import benzinga
from ..providers.finnhub import finnhub
from ..providers.polygon import polygon
from ..providers.quiver import quiver
from ..providers.tradier import tradier

router = APIRouter(tags=["meta"])
settings = get_settings()


@router.get("/providers")
def providers():
    """Which data providers and alert channels are active, and who serves market data."""
    market = "mock" if settings.use_mock_data else ("tradier" if tradier.configured else "polygon")
    return {
        "market_data_provider": market,
        "providers": {
            "tradier": tradier.configured,
            "polygon": polygon.configured,
            "finnhub": finnhub.configured,
            "alpha_vantage": alphavantage.configured,
            "benzinga": benzinga.configured,
            "quiver_congress": quiver.configured,
            "sec_edgar": True,  # keyless
            "anthropic": bool(settings.anthropic_api_key),
            "mock": settings.use_mock_data,
        },
        "alert_channels": {
            "telegram": bool(settings.telegram_bot_token and settings.telegram_chat_id),
            "discord": bool(settings.discord_webhook_url),
            "slack": bool(settings.slack_webhook_url),
            "smtp_email": bool(settings.smtp_host and settings.alert_email_to),
            "sendgrid_email": bool(settings.sendgrid_api_key and settings.alert_email),
            "twilio_sms": bool(
                settings.twilio_account_sid and settings.twilio_auth_token
                and settings.twilio_from and settings.alert_phone
            ),
            "ntfy_push": bool(settings.ntfy_topic),
        },
    }


@router.get("/momentum")
def momentum_rankings(limit: int = 20):
    """Cached momentum ranking across the liquid-options universe.
    Research ranking only — not investment advice."""
    return momentum.snapshot(limit=limit)


@router.post("/momentum/refresh", status_code=202)
def momentum_refresh():
    started = momentum.refresh_async()
    return {"started": started, "scanning": True}


class MomentumAdd(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)


@router.get("/momentum/universe")
def momentum_universe(db: Session = Depends(get_db)):
    items = db.scalars(select(MomentumItem).order_by(MomentumItem.symbol)).all()
    return {
        "symbols": [{"id": i.id, "symbol": i.symbol, "added_at": i.added_at} for i in items],
        "fallback": len(items) == 0,  # empty list → board uses watchlist + base ETFs
    }


@router.post("/momentum/universe", status_code=201)
def momentum_universe_add(payload: MomentumAdd, db: Session = Depends(get_db)):
    symbol = payload.symbol.strip().upper()
    if db.scalar(select(MomentumItem).where(MomentumItem.symbol == symbol)):
        raise HTTPException(status_code=409, detail=f"{symbol} already on momentum list")
    if (db.scalar(select(func.count()).select_from(MomentumItem)) or 0) >= 50:
        raise HTTPException(status_code=400, detail="Momentum list full (50 max)")
    item = MomentumItem(symbol=symbol)
    db.add(item)
    db.commit()
    momentum.refresh_async()  # score the new ticker within seconds, not 15 min
    return {"id": item.id, "symbol": item.symbol}


@router.delete("/momentum/universe/{symbol}", status_code=204)
def momentum_universe_remove(symbol: str, db: Session = Depends(get_db)):
    item = db.scalar(select(MomentumItem).where(MomentumItem.symbol == symbol.upper()))
    if not item:
        raise HTTPException(status_code=404, detail=f"{symbol} not on momentum list")
    db.delete(item)
    db.commit()
    # Removal is visible immediately via read-time filtering; still kick a refresh
    # because deleting the last item flips the board back to the (larger) watchlist
    # universe, which needs scoring.
    momentum.refresh_async()
    return None


@router.get("/congress")
def congress_leaderboard(window: int = 90):
    """Aggregated congressional trading leaderboard. Research only — disclosures
    lag up to 45 days; never a timing signal."""
    if not quiver.configured:
        return {"error": "QUIVER_API_KEY not configured", "rows": []}
    data = quiver.congress_leaderboard(window_days=max(7, min(window, 365)))
    return data or {"error": "Quiver fetch failed", "rows": []}


@router.get("/settings")
def effective_settings():
    """Scanner thresholds and contract filters currently in force (env-configured)."""
    return {
        "scan_interval_minutes": settings.scan_interval_minutes,
        "market_hours_only": settings.market_hours_only,
        "call_score_threshold": settings.call_score_threshold,
        "put_score_threshold": settings.put_score_threshold,
        "alert_cooldown_minutes": settings.alert_cooldown_minutes,
        "contract_filters": {
            "min_dte": settings.min_dte,
            "max_dte": settings.max_dte,
            "min_open_interest": settings.min_open_interest,
            "min_volume": settings.min_volume,
            "max_spread_pct": settings.max_spread_pct,
            "min_abs_delta": settings.min_abs_delta,
            "max_abs_delta": settings.max_abs_delta,
        },
        "default_watchlist": settings.default_watchlist,
        "max_watchlist": settings.max_watchlist,
        "market_benchmark": settings.market_benchmark,
    }
