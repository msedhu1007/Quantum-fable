from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import WatchlistItem

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
settings = get_settings()


class WatchlistAdd(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)


@router.get("")
def list_watchlist(db: Session = Depends(get_db)):
    items = db.scalars(select(WatchlistItem).order_by(WatchlistItem.symbol)).all()
    return [
        {"id": i.id, "symbol": i.symbol, "enabled": i.enabled, "added_at": i.added_at}
        for i in items
    ]


@router.post("", status_code=201)
def add_symbol(payload: WatchlistAdd, db: Session = Depends(get_db)):
    symbol = payload.symbol.strip().upper()
    existing = db.scalar(select(WatchlistItem).where(WatchlistItem.symbol == symbol))
    if existing:
        raise HTTPException(status_code=409, detail=f"{symbol} already on watchlist")
    count = db.scalar(select(func.count()).select_from(WatchlistItem))
    if count >= settings.max_watchlist:
        raise HTTPException(status_code=400, detail=f"Watchlist full ({settings.max_watchlist} max)")
    item = WatchlistItem(symbol=symbol)
    db.add(item)
    db.commit()
    return {"id": item.id, "symbol": item.symbol}


@router.delete("/{symbol}", status_code=204)
def remove_symbol(symbol: str, db: Session = Depends(get_db)):
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.symbol == symbol.upper()))
    if not item:
        raise HTTPException(status_code=404, detail=f"{symbol} not on watchlist")
    db.delete(item)
    db.commit()
