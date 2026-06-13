"""Momentum ranking across the user's watchlist universe.

Technicals-only scoring (no options chains) so sweeps stay fast and inside API
rate limits. Results are cached in-process; a background refresh runs on startup
and on a schedule. Expanding a row in the UI calls /research/{ticker} for the
full options-aware picture on demand.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .models import MomentumItem, WatchlistItem

log = logging.getLogger(__name__)
settings = get_settings()

BASE_ETFS = {"SPY", "QQQ", "IWM", "SMH"}

_lock = threading.Lock()
_cache: dict = {"updated_at": None, "scanning": False, "results": [], "pending": False}


def universe() -> tuple[list[str], bool]:
    """Momentum-list tickers; falls back to watchlist + base ETFs when the
    momentum list is empty. Returns (symbols, using_fallback)."""
    with SessionLocal() as db:
        symbols = set(
            db.scalars(select(MomentumItem.symbol).where(MomentumItem.enabled.is_(True))).all()
        )
        if symbols:
            return sorted(symbols), False
        symbols = set(
            db.scalars(select(WatchlistItem.symbol).where(WatchlistItem.enabled.is_(True))).all()
        )
    symbols.update(BASE_ETFS)
    return sorted(symbols), True


def _momentum_score(ind: dict) -> int:
    """Pure-technical momentum score, -100..100. Direction = sign."""
    score = 0
    price = ind.get("price")
    if price is None:
        return 0
    for ma_key, pts in (("ema_9", 10), ("sma_20", 10), ("sma_50", 10), ("sma_200", 10)):
        ma = ind.get(ma_key)
        if ma is not None:
            score += pts if price > ma else -pts
    rsi = ind.get("rsi_14")
    if rsi is not None:
        if rsi >= 65:
            score += 15
        elif rsi >= 55:
            score += 8
        elif rsi <= 35:
            score -= 15
        elif rsi <= 45:
            score -= 8
    macd = ind.get("macd")
    if macd:
        score += 10 if macd["histogram"] > 0 else -10
    if ind.get("breakout"):
        score += 20
    if ind.get("breakdown"):
        score -= 20
    rel_vol = ind.get("relative_volume") or 0
    if rel_vol > 1.5:  # volume confirms whichever direction we lean
        score = int(score * 1.25)
    return max(-100, min(100, score))


def _scan_one(symbol: str) -> dict | None:
    # Imported here to avoid a circular import at module load
    from .scanner import _indicators

    try:
        ind = _indicators(symbol)
    except Exception:
        log.exception("Momentum scan failed for %s", symbol)
        return None
    if ind.get("price") is None:
        return None
    score = _momentum_score(ind)
    return {
        "symbol": symbol,
        "momentum_score": score,
        "direction": "CALL" if score > 0 else "PUT" if score < 0 else "FLAT",
        "price": ind.get("price"),
        "change_pct": ind.get("change_pct"),
        "rsi_14": ind.get("rsi_14"),
        "relative_volume": ind.get("relative_volume"),
        "technical_rating": ind.get("technical_rating"),
        "breakout": ind.get("breakout", False),
        "breakdown": ind.get("breakdown", False),
        "sma_20": ind.get("sma_20"),
        "sma_50": ind.get("sma_50"),
    }


def refresh(max_workers: int = 2) -> None:
    """Scan the universe and update the cache. Two workers keeps Alpha Vantage
    under its 75 req/min ceiling (~2 calls per ticker)."""
    with _lock:
        if _cache["scanning"]:
            return
        _cache["scanning"] = True
    try:
        results: list[dict] = []
        symbols, _ = universe()
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_scan_one, s): s for s in symbols}
            for fut in as_completed(futures):
                row = fut.result()
                if row:
                    results.append(row)
        results.sort(key=lambda r: abs(r["momentum_score"]), reverse=True)
        with _lock:
            _cache["results"] = results
            _cache["updated_at"] = datetime.now(timezone.utc).isoformat()
        log.info("Momentum scan complete: %d tickers ranked", len(results))
    finally:
        with _lock:
            _cache["scanning"] = False
            rerun = _cache["pending"]
            _cache["pending"] = False
        if rerun:  # universe changed mid-sweep — run once more so nothing is missed
            threading.Thread(target=refresh, daemon=True).start()


def refresh_async() -> bool:
    """Kick a refresh in a daemon thread. If a sweep is already running, queue a
    trailing one so universe changes made mid-sweep still get scored."""
    with _lock:
        if _cache["scanning"]:
            _cache["pending"] = True
            return False
    threading.Thread(target=refresh, daemon=True).start()
    return True


def snapshot(limit: int = 20) -> dict:
    """Cached rankings filtered to the *current* universe — a ticker removed from
    the list disappears immediately, without waiting for the next sweep."""
    current, fallback = universe()
    allowed = set(current)
    with _lock:
        rows = [r for r in _cache["results"] if r["symbol"] in allowed]
        return {
            "updated_at": _cache["updated_at"],
            "scanning": _cache["scanning"],
            "using_watchlist_fallback": fallback,
            "results": rows[:limit],
        }
