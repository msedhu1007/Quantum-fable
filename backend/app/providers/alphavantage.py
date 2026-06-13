"""Alpha Vantage client — real-time quotes, daily history, fundamentals,
scored news sentiment, earnings calendar.

Premium plan ($49.99, 75 req/min) unlocks real-time US quotes and removes the
25-req/day free cap. Replaces Finnhub as the stock-data + sentiment source:
quote/history normalize to the Tradier dict shapes, get_metrics matches the
Finnhub fundamentals shape, news_sentiment returns -1..1 like Finnhub did.
"""
import csv
import io
import logging
import threading
import time
from datetime import datetime

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


def _f(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class AlphaVantageClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.alpha_vantage_base_url,
            params={"apikey": settings.alpha_vantage_api_key},
            timeout=30.0,
        )
        self._entitlement_warned = False
        self._history_cache: dict[str, tuple[float, list[dict]]] = {}
        self._cache_lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(settings.alpha_vantage_api_key)

    def _get(self, params: dict) -> dict:
        resp = self._client.get("/query", params=params)
        resp.raise_for_status()
        data = resp.json()
        # AV reports plan/limit problems inside a 200 body
        for key in ("Note", "Information", "Error Message"):
            if isinstance(data, dict) and data.get(key):
                # Key not entitled to realtime/delayed yet — retry as end-of-day
                if params.get("entitlement") and "not yet entitled" in data[key]:
                    if not self._entitlement_warned:
                        log.warning("Alpha Vantage key lacks '%s' entitlement — using end-of-day data. "
                                    "Check that the premium key is the one in .env.", params["entitlement"])
                        self._entitlement_warned = True
                    return self._get({k: v for k, v in params.items() if k != "entitlement"})
                raise httpx.HTTPError(f"Alpha Vantage: {data[key][:120]}")
        return data

    def get_quote(self, symbol: str) -> dict | None:
        try:
            data = self._get({
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "entitlement": "realtime",  # premium plans: live instead of EOD quote
            })
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("AV quote failed for %s: %s", symbol, exc)
            return None
        q = data.get("Global Quote") or {}
        price = _f(q.get("05. price"))
        if price is None:
            return None
        return {
            "last": price,
            "volume": _f(q.get("06. volume")),
            "change_percentage": _f((q.get("10. change percent") or "").rstrip("%")),
            "prev_close": _f(q.get("08. previous close")),
        }

    def get_daily_history(self, symbol: str, start: str, end: str) -> list[dict]:
        # The full daily series is a multi-MB payload — cache 10 min per symbol
        with self._cache_lock:
            hit = self._history_cache.get(symbol)
        if hit and time.monotonic() - hit[0] < 600:
            return [b for b in hit[1] if start <= b["date"] <= end]
        try:
            data = self._get({
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "outputsize": "full",
                "entitlement": "realtime",
            })
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("AV history failed for %s: %s", symbol, exc)
            return []
        series = data.get("Time Series (Daily)") or {}
        all_bars = []
        for day in sorted(series):
            bar = series[day]
            all_bars.append({
                "date": day,
                "open": _f(bar.get("1. open")),
                "high": _f(bar.get("2. high")),
                "low": _f(bar.get("3. low")),
                "close": _f(bar.get("4. close")),
                "volume": _f(bar.get("5. volume")),
            })
        # Keep ~2 years cached; enough for SMA200 + 52-week stats
        all_bars = all_bars[-520:]
        with self._cache_lock:
            self._history_cache[symbol] = (time.monotonic(), all_bars)
        return [b for b in all_bars if start <= b["date"] <= end]

    def get_metrics(self, symbol: str) -> dict | None:
        """Company fundamentals from OVERVIEW, in the Finnhub metrics shape."""
        try:
            ov = self._get({"function": "OVERVIEW", "symbol": symbol})
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("AV overview failed for %s: %s", symbol, exc)
            return None
        if not ov.get("Symbol"):
            return None
        mc = _f(ov.get("MarketCapitalization"))
        rev_g = _f(ov.get("QuarterlyRevenueGrowthYOY"))
        eps_g = _f(ov.get("QuarterlyEarningsGrowthYOY"))
        margin = _f(ov.get("ProfitMargin"))
        roe = _f(ov.get("ReturnOnEquityTTM"))
        return {
            "market_cap": mc / 1e6 if mc else None,  # Finnhub shape uses $ millions
            "pe": _f(ov.get("TrailingPE")),
            "forward_pe": _f(ov.get("ForwardPE")),
            "ps": _f(ov.get("PriceToSalesRatioTTM")),
            "revenue_growth_yoy": rev_g * 100 if rev_g is not None else None,
            "eps_growth_yoy": eps_g * 100 if eps_g is not None else None,
            "net_margin": margin * 100 if margin is not None else None,
            "roe": roe * 100 if roe is not None else None,
            "debt_to_equity": None,  # not in OVERVIEW
            "beta": _f(ov.get("Beta")),
            "52w_high": _f(ov.get("52WeekHigh")),
            "52w_low": _f(ov.get("52WeekLow")),
            "sector": ov.get("Sector"),
            "industry": ov.get("Industry"),
            "analyst_target": _f(ov.get("AnalystTargetPrice")),
        }

    def news_sentiment(self, symbol: str, limit: int = 50) -> float | None:
        """Mean AV ticker-level sentiment score, already on a -1..1 scale."""
        try:
            data = self._get({
                "function": "NEWS_SENTIMENT",
                "tickers": symbol,
                "limit": limit,
                "sort": "LATEST",
            })
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("AV news sentiment failed for %s: %s", symbol, exc)
            return None
        scores = []
        for item in data.get("feed") or []:
            for ts in item.get("ticker_sentiment") or []:
                if ts.get("ticker") == symbol:
                    score = _f(ts.get("ticker_sentiment_score"))
                    relevance = _f(ts.get("relevance_score")) or 0
                    if score is not None and relevance >= 0.2:
                        scores.append(score)
        if not scores:
            return None
        return round(sum(scores) / len(scores), 3)

    def company_news(self, symbol: str, limit: int = 15) -> list[dict]:
        """Headlines from NEWS_SENTIMENT, normalized to the scanner's news shape."""
        try:
            data = self._get({
                "function": "NEWS_SENTIMENT",
                "tickers": symbol,
                "limit": limit,
                "sort": "LATEST",
            })
        except (httpx.HTTPError, ValueError):
            return []
        news = []
        for item in (data.get("feed") or [])[:limit]:
            published = None
            try:  # AV format: 20260611T143000
                published = int(datetime.strptime(item["time_published"], "%Y%m%dT%H%M%S").timestamp())
            except (KeyError, TypeError, ValueError):
                pass
            news.append({
                "headline": item.get("title"),
                "source": item.get("source"),
                "url": item.get("url"),
                "datetime": published,
                "sentiment_label": item.get("overall_sentiment_label"),
            })
        return news

    def next_earnings(self, symbol: str) -> dict | None:
        """Next earnings date from the EARNINGS_CALENDAR CSV endpoint."""
        try:
            resp = self._client.get("/query", params={
                "function": "EARNINGS_CALENDAR",
                "symbol": symbol,
                "horizon": "3month",
            })
            resp.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(resp.text)))
        except (httpx.HTTPError, csv.Error) as exc:
            log.warning("AV earnings calendar failed for %s: %s", symbol, exc)
            return None
        if not rows:
            return None
        row = rows[0]
        return {"date": row.get("reportDate"), "estimate": _f(row.get("estimate"))}


alphavantage = AlphaVantageClient()
