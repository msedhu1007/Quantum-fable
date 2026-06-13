"""Yahoo Finance quote — keyless, includes real-time pre/post-market trades.

Uses the public v8 chart endpoint (same source the yfinance library wraps,
without the pandas dependency). Last 1-minute bar with includePrePost=true is
the latest extended-hours print. Used as the after-hours price source; intraday
the Finnhub real-time quote already wins on freshness.
"""
import logging

import httpx

log = logging.getLogger(__name__)

_client = httpx.Client(
    base_url="https://query1.finance.yahoo.com",
    headers={"User-Agent": "Mozilla/5.0 (options-research-tool)"},
    timeout=10.0,
)


class YahooClient:
    configured = True  # keyless

    def get_quote(self, symbol: str) -> dict | None:
        try:
            resp = _client.get(
                f"/v8/finance/chart/{symbol}",
                params={"interval": "1m", "range": "1d", "includePrePost": "true"},
            )
            resp.raise_for_status()
            result = (resp.json().get("chart") or {}).get("result") or []
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Yahoo quote failed for %s: %s", symbol, exc)
            return None
        if not result:
            return None
        chart = result[0]
        meta = chart.get("meta") or {}
        timestamps = chart.get("timestamp") or []
        closes = ((chart.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
        # Walk back to the most recent non-null 1-minute close (extended hours included)
        last, ts = None, None
        for i in range(len(closes) - 1, -1, -1):
            if closes[i] is not None:
                last, ts = closes[i], timestamps[i] if i < len(timestamps) else None
                break
        if last is None:
            last, ts = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
        if last is None:
            return None
        prev_close = meta.get("chartPreviousClose")
        change_pct = None
        if prev_close:
            change_pct = round((last - prev_close) / prev_close * 100, 2)
        return {
            "last": round(float(last), 4),
            "volume": None,
            "change_percentage": change_pct,
            "prev_close": prev_close,
            "quote_time": ts,
        }


yahoo = YahooClient()
