"""Tradier market-data client — quotes, history, options chains with Greeks (via ORATS)."""
import logging

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


class TradierClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.tradier_base_url,
            headers={
                "Authorization": f"Bearer {settings.tradier_api_key}",
                "Accept": "application/json",
            },
            timeout=20.0,
        )

    @property
    def configured(self) -> bool:
        return bool(settings.tradier_api_key)

    def _get(self, path: str, params: dict) -> dict:
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_quote(self, symbol: str) -> dict | None:
        data = self._get("/markets/quotes", {"symbols": symbol})
        quote = (data.get("quotes") or {}).get("quote")
        if isinstance(quote, list):
            quote = quote[0] if quote else None
        return quote

    def get_daily_history(self, symbol: str, start: str, end: str) -> list[dict]:
        data = self._get(
            "/markets/history",
            {"symbol": symbol, "interval": "daily", "start": start, "end": end},
        )
        days = (data.get("history") or {}).get("day") or []
        if isinstance(days, dict):
            days = [days]
        return days

    def get_expirations(self, symbol: str) -> list[str]:
        data = self._get(
            "/markets/options/expirations",
            {"symbol": symbol, "includeAllRoots": "true", "strikes": "false"},
        )
        dates = (data.get("expirations") or {}).get("date") or []
        if isinstance(dates, str):
            dates = [dates]
        return dates

    def get_chain(self, symbol: str, expiration: str) -> list[dict]:
        data = self._get(
            "/markets/options/chains",
            {"symbol": symbol, "expiration": expiration, "greeks": "true"},
        )
        options = (data.get("options") or {}).get("option") or []
        if isinstance(options, dict):
            options = [options]
        return options


tradier = TradierClient()
