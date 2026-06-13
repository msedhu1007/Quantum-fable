"""Finnhub client — company news, news sentiment, earnings calendar."""
import logging
from datetime import date, timedelta

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


class FinnhubClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.finnhub_base_url,
            params={"token": settings.finnhub_api_key},
            timeout=20.0,
        )

    @property
    def configured(self) -> bool:
        return bool(settings.finnhub_api_key)

    def _get(self, path: str, params: dict) -> dict | list:
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_quote(self, symbol: str) -> dict | None:
        """Real-time quote (free tier), normalized to the Tradier quote shape.
        Finnhub /quote has no volume field — callers keep volume from history."""
        try:
            data = self._get("/quote", {"symbol": symbol})
        except httpx.HTTPError:
            return None
        if not isinstance(data, dict) or not data.get("c"):
            return None
        return {
            "last": data["c"],
            "volume": None,
            "change_percentage": data.get("dp"),
            "prev_close": data.get("pc"),
            "quote_time": data.get("t"),
        }

    def get_metrics(self, symbol: str) -> dict | None:
        """Key fundamentals from /stock/metric (free tier)."""
        try:
            data = self._get("/stock/metric", {"symbol": symbol, "metric": "all"})
        except (httpx.HTTPError, ValueError):
            return None
        metric = (data or {}).get("metric") or {}
        if not metric:
            return None
        return {
            "market_cap": metric.get("marketCapitalization"),
            "pe": metric.get("peTTM"),
            "ps": metric.get("psTTM"),
            "revenue_growth_yoy": metric.get("revenueGrowthTTMYoy"),
            "eps_growth_yoy": metric.get("epsGrowthTTMYoy"),
            "net_margin": metric.get("netProfitMarginTTM"),
            "operating_margin": metric.get("operatingMarginTTM"),
            "roe": metric.get("roeTTM"),
            "debt_to_equity": metric.get("totalDebt/totalEquityQuarterly"),
            "current_ratio": metric.get("currentRatioQuarterly"),
            "52w_high": metric.get("52WeekHigh"),
            "52w_low": metric.get("52WeekLow"),
            "beta": metric.get("beta"),
        }

    def company_news(self, symbol: str, days_back: int = 3) -> list[dict]:
        today = date.today()
        try:
            items = self._get(
                "/company-news",
                {
                    "symbol": symbol,
                    "from": (today - timedelta(days=days_back)).isoformat(),
                    "to": today.isoformat(),
                },
            )
        except (httpx.HTTPError, ValueError):
            log.warning("Finnhub company-news failed for %s (expired key?)", symbol)
            return []
        return items if isinstance(items, list) else []

    def news_sentiment(self, symbol: str) -> float | None:
        """Return sentiment normalized to -1..1, or None when unavailable."""
        try:
            data = self._get("/news-sentiment", {"symbol": symbol})
        except httpx.HTTPError:
            return None
        if not isinstance(data, dict):
            return None
        # companyNewsScore is 0..1; bullishPercent fallback also 0..1
        score = data.get("companyNewsScore")
        if score is None:
            score = (data.get("sentiment") or {}).get("bullishPercent")
        if score is None:
            return None
        return (float(score) - 0.5) * 2

    def next_earnings(self, symbol: str, days_ahead: int = 21) -> dict | None:
        today = date.today()
        try:
            data = self._get(
                "/calendar/earnings",
                {
                    "symbol": symbol,
                    "from": today.isoformat(),
                    "to": (today + timedelta(days=days_ahead)).isoformat(),
                },
            )
        except httpx.HTTPError:
            return None
        events = (data or {}).get("earningsCalendar") or []
        return events[0] if events else None


finnhub = FinnhubClient()
