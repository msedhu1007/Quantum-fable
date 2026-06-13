from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..scanner import market_provider, scan_all, scan_ticker

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("")
def trigger_scan_all():
    """Manually scan the whole watchlist (ignores schedule, respects market-hours setting)."""
    return scan_all()


@router.post("/{ticker}")
def trigger_scan(ticker: str, db: Session = Depends(get_db)):
    if not market_provider().configured:
        raise HTTPException(status_code=503, detail="No market data provider configured (TRADIER_API_KEY or POLYGON_API_KEY)")
    return scan_ticker(ticker.upper(), db)
