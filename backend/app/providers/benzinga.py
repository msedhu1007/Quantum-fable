"""Benzinga news client — recent headlines per ticker, normalized to the
{headline, source, url, datetime} shape the scanner stores."""
import logging
from datetime import date, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


class BenzingaClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.benzinga_base_url,
            params={"token": settings.benzinga_api_key},
            headers={"Accept": "application/json"},
            timeout=20.0,
        )

    @property
    def configured(self) -> bool:
        return bool(settings.benzinga_api_key)

    def company_news(self, symbol: str, days_back: int = 3, limit: int = 15) -> list[dict]:
        try:
            resp = self._client.get(
                "/news",
                params={
                    "tickers": symbol,
                    "dateFrom": (date.today() - timedelta(days=days_back)).isoformat(),
                    "pageSize": limit,
                    "displayOutput": "abstract",
                },
            )
            resp.raise_for_status()
            items = resp.json()
        except (httpx.HTTPError, ValueError):
            log.exception("Benzinga news fetch failed for %s", symbol)
            return []
        if not isinstance(items, list):
            return []
        news = []
        for item in items:
            published = None
            try:
                # Benzinga "created" is RFC 2822, e.g. "Wed, 11 Jun 2026 09:30:00 -0400"
                published = int(parsedate_to_datetime(item["created"]).astimezone(timezone.utc).timestamp())
            except (KeyError, TypeError, ValueError):
                pass
            news.append({
                "headline": item.get("title"),
                "source": "Benzinga",
                "url": item.get("url"),
                "datetime": published,
            })
        return news


benzinga = BenzingaClient()
