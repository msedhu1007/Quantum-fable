"""Deterministic signal scoring and options contract filters.

Hard rules run first; the LLM layer (analyst.py) only explains and classifies
setups that already pass these filters. Score range is roughly -85..+85.
"""
from datetime import date, datetime

from .config import get_settings

settings = get_settings()


RATING_WEIGHTS = {
    # category: (strong, mild) — sign follows bullish/bearish direction
    "technical": (30, 15),
    "fundamental": (20, 10),
}


def _rating_points(rating: str | None, strong: int, mild: int) -> int:
    return {
        "strong_bullish": strong,
        "mild_bullish": mild,
        "mild_bearish": -mild,
        "strong_bearish": -strong,
    }.get(rating or "", 0)


def rate_fundamentals(metrics: dict | None) -> str:
    """Five-level fundamental rating from Finnhub key metrics."""
    if not metrics:
        return "neutral"
    votes = 0
    rev = metrics.get("revenue_growth_yoy")
    if rev is not None:
        votes += 1 if rev > 10 else (-1 if rev < 0 else 0)
    eps = metrics.get("eps_growth_yoy")
    if eps is not None:
        votes += 1 if eps > 10 else (-1 if eps < 0 else 0)
    margin = metrics.get("net_margin")
    if margin is not None:
        votes += 1 if margin > 15 else (-1 if margin < 0 else 0)
    roe = metrics.get("roe")
    if roe is not None:
        votes += 1 if roe > 15 else (-1 if roe < 0 else 0)
    dte_ratio = metrics.get("debt_to_equity")
    if dte_ratio is not None:
        votes += -1 if dte_ratio > 2 else 0

    if votes >= 3:
        return "strong_bullish"
    if votes >= 1:
        return "mild_bullish"
    if votes <= -3:
        return "strong_bearish"
    if votes <= -1:
        return "mild_bearish"
    return "neutral"


def score_signal(data: dict) -> int:
    """Score a ticker from bearish (-100) to bullish (+100)."""
    score = 0

    # Technical rating (from technicals.compute); volume confirmation nudges mild → stronger
    tech = data.get("technical_rating")
    tech_points = _rating_points(tech, *RATING_WEIGHTS["technical"])
    rel_vol = data.get("relative_volume") or 0
    if tech_points and abs(tech_points) == RATING_WEIGHTS["technical"][1] and rel_vol > 1.5:
        tech_points = int(tech_points * 1.5)
    score += tech_points

    # Fundamental rating
    score += _rating_points(data.get("fundamental_rating"), *RATING_WEIGHTS["fundamental"])

    # News sentiment (normalized -1..1)
    sentiment = data.get("news_sentiment")
    if sentiment is not None:
        if sentiment > 0.5:
            score += 25
        elif sentiment > 0.2:
            score += 10
        elif sentiment < -0.5:
            score -= 25
        elif sentiment < -0.2:
            score -= 10

    # Options flow
    call_ratio = data.get("call_volume_ratio") or 0  # call vol / put vol
    put_ratio = data.get("put_volume_ratio") or 0    # put vol / call vol
    if call_ratio > 2.0:
        score += 20
    elif call_ratio > 1.5:
        score += 10
    elif put_ratio > 2.0:
        score -= 20
    elif put_ratio > 1.5:
        score -= 10

    # Market regime
    trend = data.get("market_trend")
    if trend == "bullish":
        score += 10
    elif trend == "bearish":
        score -= 10

    # IV risk penalty — elevated IV makes premium expensive in either direction
    iv_pct = data.get("iv_percentile")
    if iv_pct is not None and iv_pct > 85:
        score = int(score * 0.75)

    return max(-100, min(100, round(score)))


def _dte(expiration: str) -> int:
    exp = datetime.strptime(expiration, "%Y-%m-%d").date()
    return (exp - date.today()).days


def spread_pct(bid: float | None, ask: float | None) -> float | None:
    if not bid or not ask or ask <= 0:
        return None
    mid = (bid + ask) / 2
    if mid <= 0:
        return None
    return (ask - bid) / mid * 100


def contract_passes_filters(opt: dict) -> bool:
    """Liquidity / delta / DTE / spread hard rules from the blueprint."""
    try:
        dte = _dte(opt["expiration_date"])
    except (KeyError, ValueError):
        return False
    if not settings.min_dte <= dte <= settings.max_dte:
        return False
    if (opt.get("open_interest") or 0) < settings.min_open_interest:
        return False
    if (opt.get("volume") or 0) < settings.min_volume:
        return False
    sp = spread_pct(opt.get("bid"), opt.get("ask"))
    if sp is None or sp > settings.max_spread_pct:
        return False
    delta = (opt.get("greeks") or {}).get("delta")
    if delta is None:
        return False
    return settings.min_abs_delta <= abs(delta) <= settings.max_abs_delta


def find_best_contract(options: list[dict], option_type: str) -> dict | None:
    """Pick the most liquid contract of the given type that passes filters."""
    candidates = [
        o for o in options
        if o.get("option_type") == option_type and contract_passes_filters(o)
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda o: ((o.get("volume") or 0), (o.get("open_interest") or 0)))
    greeks = best.get("greeks") or {}
    return {
        "symbol": best.get("symbol"),
        "description": best.get("description"),
        "option_type": option_type,
        "strike": best.get("strike"),
        "expiration": best.get("expiration_date"),
        "dte": _dte(best["expiration_date"]),
        "delta": greeks.get("delta"),
        "iv": greeks.get("mid_iv") or greeks.get("smv_vol"),
        "volume": best.get("volume"),
        "open_interest": best.get("open_interest"),
        "bid": best.get("bid"),
        "ask": best.get("ask"),
        "spread_pct": round(spread_pct(best.get("bid"), best.get("ask")) or 0, 2),
    }


def make_alert(ticker: str, score: int, best_call: dict | None, best_put: dict | None) -> dict:
    if score >= settings.call_score_threshold and best_call:
        return {
            "decision": "CALL",
            "ticker": ticker,
            "score": score,
            "contract": best_call,
            "message": f"Potential CALL setup on {ticker}. Score: {score}/100.",
        }
    if score <= settings.put_score_threshold and best_put:
        return {
            "decision": "PUT",
            "ticker": ticker,
            "score": abs(score),
            "contract": best_put,
            "message": f"Potential PUT setup on {ticker}. Score: {abs(score)}/100.",
        }
    return {
        "decision": "NO TRADE",
        "ticker": ticker,
        "score": score,
        "contract": None,
        "message": f"No high-confidence options setup for {ticker}.",
    }
