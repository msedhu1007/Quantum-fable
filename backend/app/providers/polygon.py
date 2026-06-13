"""Polygon.io market-data client — quotes, daily aggregates, options chain snapshots.

Exposes the same method surface as TradierClient (get_quote, get_daily_history,
get_expirations, get_chain) and normalizes responses to the Tradier dict shapes the
scanner and scoring modules expect, so the two providers are interchangeable.

Plan notes: stock aggregates work on the free tier (delayed). The options chain
snapshot endpoint requires an options plan — on a 403 the chain methods return
empty lists and the scanner degrades to a no-options-flow scan.
"""
import logging
from datetime import date

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

MAX_CHAIN_PAGES = 4  # 250 contracts/page


class PolygonClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.polygon_base_url,
            headers={"Authorization": f"Bearer {settings.polygon_api_key}"},
            timeout=20.0,
        )
        self._options_denied = False

    @property
    def configured(self) -> bool:
        return bool(settings.polygon_api_key)

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = self._client.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    def get_quote(self, symbol: str) -> dict | None:
        """Last price / volume / day change, normalized to Tradier quote keys."""
        try:
            data = self._get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}")
            tick = data.get("ticker") or {}
            day = tick.get("day") or {}
            last = (tick.get("lastTrade") or {}).get("p") or day.get("c")
            if last:
                return {
                    "last": last,
                    "volume": day.get("v"),
                    "change_percentage": tick.get("todaysChangePerc"),
                }
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (401, 403, 429):
                raise
        # Free tier: snapshot is gated — fall back to the previous daily bar (delayed).
        try:
            data = self._get(f"/v2/aggs/ticker/{symbol}/prev", {"adjusted": "true"})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:  # stock endpoints rate-limited on options plans
                log.warning("Polygon stock quote rate-limited for %s", symbol)
                return None
            raise
        bars = data.get("results") or []
        if not bars:
            return None
        bar = bars[0]
        change_pct = None
        if bar.get("o"):
            change_pct = round((bar["c"] - bar["o"]) / bar["o"] * 100, 2)
        return {"last": bar.get("c"), "volume": bar.get("v"), "change_percentage": change_pct}

    def get_underlying_price(self, symbol: str) -> dict | None:
        """Live(ish) underlying price from the options snapshot's underlying_asset
        block. Comes with the Options plan (15-min delayed), normalized to the
        Tradier quote shape. Volume isn't included here — callers keep it from history."""
        if self._options_denied:
            return None
        try:
            data = self._get(f"/v3/snapshot/options/{symbol}", {"limit": 1})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                self._deny_options(exc)
            return None
        results = data.get("results") or []
        if not results:
            return None
        underlying = results[0].get("underlying_asset") or {}
        price = underlying.get("price")
        if price is None:
            return None
        ts_ns = underlying.get("last_updated")
        return {"last": price, "volume": None, "change_percentage": None,
                "stale": underlying.get("timeframe") == "DELAYED",
                "quote_time": ts_ns / 1e9 if ts_ns else None}

    def get_daily_history(self, symbol: str, start: str, end: str) -> list[dict]:
        data = self._get(
            f"/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}",
            {"adjusted": "true", "sort": "asc", "limit": 500},
        )
        return [
            {
                "open": bar.get("o"),
                "high": bar.get("h"),
                "low": bar.get("l"),
                "close": bar.get("c"),
                "volume": bar.get("v"),
            }
            for bar in data.get("results") or []
        ]

    def get_expirations(self, symbol: str) -> list[str]:
        if self._options_denied:
            return []
        try:
            data = self._get(
                "/v3/reference/options/contracts",
                {
                    "underlying_ticker": symbol,
                    "expiration_date.gte": date.today().isoformat(),
                    "limit": 1000,
                    "sort": "expiration_date",
                },
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                self._deny_options(exc)
                return []
            raise
        seen: dict[str, None] = {}
        for contract in data.get("results") or []:
            exp = contract.get("expiration_date")
            if exp:
                seen.setdefault(exp)
        return list(seen)

    def get_chain(self, symbol: str, expiration: str) -> list[dict]:
        """Full chain snapshot for one expiration, in Tradier option-dict shape."""
        if self._options_denied:
            return []
        options: list[dict] = []
        url: str | None = f"/v3/snapshot/options/{symbol}"
        params: dict | None = {"expiration_date": expiration, "limit": 250}
        for _ in range(MAX_CHAIN_PAGES):
            if not url:
                break
            try:
                data = self._get(url, params)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    self._deny_options(exc)
                    return []
                raise
            for item in data.get("results") or []:
                details = item.get("details") or {}
                quote = item.get("last_quote") or {}
                greeks = item.get("greeks") or {}
                options.append({
                    "symbol": details.get("ticker"),
                    "description": details.get("ticker"),
                    "option_type": details.get("contract_type"),
                    "expiration_date": details.get("expiration_date"),
                    "strike": details.get("strike_price"),
                    "bid": quote.get("bid"),
                    "ask": quote.get("ask"),
                    "volume": (item.get("day") or {}).get("volume"),
                    "open_interest": item.get("open_interest"),
                    "greeks": {
                        "delta": greeks.get("delta"),
                        "mid_iv": item.get("implied_volatility"),
                    },
                })
            # next_url is absolute; httpx base_url handles it either way
            url, params = data.get("next_url"), None
        return options

    def _deny_options(self, exc: httpx.HTTPStatusError) -> None:
        if not self._options_denied:
            log.warning(
                "Polygon options endpoints denied (HTTP %s) — current plan lacks options data; "
                "scans will run without options flow / contract candidates",
                exc.response.status_code,
            )
        self._options_denied = True


polygon = PolygonClient()
