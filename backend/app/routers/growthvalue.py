"""Growth & Value board: dedicated universe, ranked scores, per-ticker scorecard.

Research scorecards only — simplified, fundamentals-only. Not investment advice.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import growthvalue
from ..db import get_db
from ..models import GrowthValueItem, GrowthValueNote

router = APIRouter(prefix="/growth-value", tags=["growth-value"])

MAX_UNIVERSE = 50


# Static routes are declared before the /{ticker} path param so they win the match.
@router.get("")
def board(limit: int = 50, sort_by: str = "growth"):
    """Cached Growth/Value ranking across the board's universe."""
    return growthvalue.snapshot(limit=limit, sort_by=sort_by)


@router.post("/refresh", status_code=202)
def refresh():
    started = growthvalue.refresh_async()
    return {"started": started, "scanning": True}


class UniverseAdd(BaseModel):
    symbol: str = Field(min_length=1, max_length=12)


@router.get("/universe")
def universe(db: Session = Depends(get_db)):
    items = db.scalars(select(GrowthValueItem).order_by(GrowthValueItem.symbol)).all()
    return {"symbols": [{"id": i.id, "symbol": i.symbol, "added_at": i.added_at} for i in items]}


@router.post("/universe", status_code=201)
def universe_add(payload: UniverseAdd, db: Session = Depends(get_db)):
    symbol = payload.symbol.strip().upper()
    if db.scalar(select(GrowthValueItem).where(GrowthValueItem.symbol == symbol)):
        raise HTTPException(status_code=409, detail=f"{symbol} already on the list")
    if (db.scalar(select(func.count()).select_from(GrowthValueItem)) or 0) >= MAX_UNIVERSE:
        raise HTTPException(status_code=400, detail=f"List full ({MAX_UNIVERSE} max)")
    item = GrowthValueItem(symbol=symbol)
    db.add(item)
    db.commit()
    growthvalue.refresh_async()  # score the new ticker within seconds
    return {"id": item.id, "symbol": item.symbol}


@router.delete("/universe/{symbol}", status_code=204)
def universe_remove(symbol: str, db: Session = Depends(get_db)):
    item = db.scalar(select(GrowthValueItem).where(GrowthValueItem.symbol == symbol.upper()))
    if not item:
        raise HTTPException(status_code=404, detail=f"{symbol} not on the list")
    db.delete(item)
    db.commit()
    return None


class NoteIn(BaseModel):
    thesis: str | None = Field(default=None, max_length=4000)
    risks: str | None = Field(default=None, max_length=4000)
    watch: str | None = Field(default=None, max_length=4000)


@router.put("/{ticker}/note")
def save_note(ticker: str, payload: NoteIn, db: Session = Depends(get_db)):
    """Upsert the human moat thesis for a ticker (why / what-breaks-it / watch)."""
    symbol = ticker.strip().upper()
    note = db.scalar(select(GrowthValueNote).where(GrowthValueNote.symbol == symbol))
    if not note:
        note = GrowthValueNote(symbol=symbol)
        db.add(note)
    note.thesis = (payload.thesis or "").strip() or None
    note.risks = (payload.risks or "").strip() or None
    note.watch = (payload.watch or "").strip() or None
    db.commit()
    return {
        "symbol": symbol,
        "thesis": note.thesis,
        "risks": note.risks,
        "watch": note.watch,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


@router.get("/{ticker}")
def ticker_scorecard(ticker: str):
    """Full Growth + Value scorecard with factor breakdowns for one ticker."""
    return growthvalue.scorecard(ticker)
