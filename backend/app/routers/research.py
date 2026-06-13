from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException

from ..providers.edgar import insider_summary
from ..providers.quiver import quiver
from ..scanner import gather_ticker_data, market_provider
from ..scoring import make_alert, score_signal

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/{ticker}")
def research(ticker: str):
    """Live research snapshot: indicators, options flow, news, score, candidates."""
    ticker = ticker.upper()
    if not market_provider().configured:
        raise HTTPException(status_code=503, detail="No market data provider configured (TRADIER_API_KEY or POLYGON_API_KEY)")
    data = gather_ticker_data(ticker)
    if data.get("price") is None:
        raise HTTPException(status_code=404, detail=f"No quote data for {ticker}")

    with ThreadPoolExecutor(max_workers=2) as pool:
        insider_fut = pool.submit(insider_summary, ticker)
        congress_fut = pool.submit(quiver.congress_summary, ticker) if quiver.configured else None

        score = score_signal(data)
        verdict = make_alert(ticker, score, data.get("best_call"), data.get("best_put"))

        data["insider_activity"] = insider_fut.result()
        if congress_fut is not None:
            data["congress_activity"] = congress_fut.result()

    return {"data": data, "score": score, "verdict": verdict}
