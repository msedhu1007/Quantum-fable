"""Quiver Quant client — congressional trading disclosures (STOCK Act).

One endpoint used: historical congress trades per ticker. Disclosures are filed
up to 45 days after the trade, so this is research context, not a timing signal.
Cached per ticker for an hour.
"""
import logging
import threading
import time
from datetime import date, timedelta

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

_CACHE_TTL = 3600.0
_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


class QuiverClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url="https://api.quiverquant.com/beta",
            headers={
                "Authorization": f"Bearer {settings.quiver_api_key}",
                "Accept": "application/json",
                "User-Agent": "QuantumFable options research",
            },
            timeout=20.0,
        )

    @property
    def configured(self) -> bool:
        return bool(settings.quiver_api_key)

    def congress_summary(self, symbol: str, limit: int = 12) -> dict | None:
        """Recent congressional trades in this ticker, newest first."""
        symbol = symbol.upper()
        with _lock:
            hit = _cache.get(symbol)
            if hit and time.monotonic() - hit[0] < _CACHE_TTL:
                return hit[1]
        try:
            resp = self._client.get(f"/historical/congresstrading/{symbol}")
            resp.raise_for_status()
            rows = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Quiver congress fetch failed for %s: %s", symbol, exc)
            return None
        if not isinstance(rows, list):
            return None

        trades = []
        for row in rows:
            txn = (row.get("Transaction") or "").lower()
            trades.append({
                "name": row.get("Representative"),
                "chamber": row.get("House"),
                "party": row.get("Party"),
                "type": "BUY" if "purchase" in txn else "SELL",
                "transaction": row.get("Transaction"),
                "range": row.get("Range"),
                "traded": row.get("TransactionDate"),
                "filed": row.get("ReportDate"),
                "excess_return_pct": row.get("ExcessReturn"),
            })
        trades.sort(key=lambda t: t.get("traded") or "", reverse=True)
        cutoff = (date.today() - timedelta(days=365)).isoformat()
        recent_window = [t for t in trades if (t.get("traded") or "") >= cutoff]
        buys = sum(1 for t in recent_window if t["type"] == "BUY")
        sells = sum(1 for t in recent_window if t["type"] == "SELL")
        summary = {
            "buys": buys,
            "sells": sells,
            "total": len(recent_window),
            "recent": trades[:limit],
            "source": "Quiver Quant — STOCK Act disclosures",
            "lag_note": "Members may file up to 45 days after trading.",
        }
        with _lock:
            _cache[symbol] = (time.monotonic(), summary)
        return summary


    def congress_leaderboard(self, window_days: int = 90) -> dict | None:
        """Aggregate the live all-tickers feed into per-ticker leaderboards:
        distinct members buying, trade counts, estimated dollar flows, party split."""
        cache_key = f"_leaderboard:{window_days}"
        with _lock:
            hit = _cache.get(cache_key)
            if hit and time.monotonic() - hit[0] < _CACHE_TTL:
                return hit[1]
        try:
            resp = self._client.get("/live/congresstrading")
            resp.raise_for_status()
            rows = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Quiver live congress fetch failed: %s", exc)
            return None
        if not isinstance(rows, list):
            return None

        cutoff = (date.today() - timedelta(days=window_days)).isoformat()
        agg: dict[str, dict] = {}
        notable: list[dict] = []
        for row in rows:
            traded = row.get("TransactionDate") or ""
            ticker = (row.get("Ticker") or "").upper()
            if traded < cutoff or not ticker or row.get("TickerType") not in (None, "Stock", "stock"):
                continue
            txn = (row.get("Transaction") or "").lower()
            is_buy = "purchase" in txn
            amount = 0.0
            try:
                amount = float(row.get("Amount") or 0)
            except (TypeError, ValueError):
                pass
            member = row.get("Representative") or "?"
            party = (row.get("Party") or "")[:1].upper()  # D / R / I

            entry = agg.setdefault(ticker, {
                "ticker": ticker, "buys": 0, "sells": 0,
                "buyers": set(), "sellers": set(),
                "buy_value": 0.0, "sell_value": 0.0,
                "dem_buys": 0, "rep_buys": 0, "last_traded": "",
            })
            if is_buy:
                entry["buys"] += 1
                entry["buyers"].add(member)
                entry["buy_value"] += amount
                if party == "D":
                    entry["dem_buys"] += 1
                elif party == "R":
                    entry["rep_buys"] += 1
            else:
                entry["sells"] += 1
                entry["sellers"].add(member)
                entry["sell_value"] += amount
            entry["last_traded"] = max(entry["last_traded"], traded)

            if amount >= 50_000:
                notable.append({
                    "ticker": ticker,
                    "name": member,
                    "party": row.get("Party"),
                    "chamber": row.get("House"),
                    "type": "BUY" if is_buy else "SELL",
                    "range": row.get("Range"),
                    "amount": amount,
                    "traded": traded,
                    "filed": row.get("ReportDate"),
                })

        leaderboard = []
        for entry in agg.values():
            leaderboard.append({
                **entry,
                "buyers": len(entry["buyers"]),
                "sellers": len(entry["sellers"]),
                "buy_value": round(entry["buy_value"]),
                "sell_value": round(entry["sell_value"]),
                "net_value": round(entry["buy_value"] - entry["sell_value"]),
            })
        leaderboard.sort(key=lambda r: (r["buyers"], r["buy_value"]), reverse=True)
        notable.sort(key=lambda t: t["amount"], reverse=True)

        summary = {
            "window_days": window_days,
            "tickers": len(leaderboard),
            "rows": leaderboard[:50],
            "notable": notable[:15],
            "source": "Quiver Quant — STOCK Act disclosures",
            "lag_note": "Members may file up to 45 days after trading; amounts are range minimums.",
        }
        with _lock:
            _cache[cache_key] = (time.monotonic(), summary)
        return summary


quiver = QuiverClient()
