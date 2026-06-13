from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _serialize(a: Alert) -> dict:
    return {
        "id": a.id,
        "symbol": a.symbol,
        "created_at": a.created_at,
        "decision": a.decision,
        "score": a.score,
        "confidence": a.confidence,
        "contract": a.contract,
        "reasons": a.reasons,
        "risks": a.risks,
        "invalidation_level": a.invalidation_level,
        "message": a.message,
        "dispatched": a.dispatched,
    }


@router.get("")
def list_alerts(
    limit: int = 50,
    symbol: str | None = None,
    actionable_only: bool = False,
    db: Session = Depends(get_db),
):
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(min(limit, 500))
    if symbol:
        stmt = stmt.where(Alert.symbol == symbol.upper())
    if actionable_only:
        stmt = stmt.where(Alert.decision != "NO TRADE")
    return [_serialize(a) for a in db.scalars(stmt).all()]


@router.get("/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _serialize(alert)
