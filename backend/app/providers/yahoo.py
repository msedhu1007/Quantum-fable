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

    # ----------------------------------------------------------------- #
    # Fundamentals (yfinance) — moat/cyclical fingerprint fields that    #
    # Alpha Vantage OVERVIEW does not expose: gross margin, FCF, D/E,    #
    # EV/Sales, forward P/E. One ``.info`` request per ticker.           #
    # ----------------------------------------------------------------- #
    def get_fundamentals(self, symbol: str) -> dict | None:
        try:
            import yfinance as yf

            info = yf.Ticker(symbol).info or {}
        except Exception as exc:  # network, parse, or rate-limit
            log.warning("Yahoo fundamentals failed for %s: %s", symbol, exc)
            return None
        if not info.get("symbol") and not info.get("shortName"):
            return None

        def pct(key: str) -> float | None:
            v = info.get(key)
            return round(v * 100, 2) if isinstance(v, (int, float)) else None

        fcf = info.get("freeCashflow")
        rev = info.get("totalRevenue")
        fcf_margin = (
            round(fcf / rev * 100, 1)
            if isinstance(fcf, (int, float)) and isinstance(rev, (int, float)) and rev
            else None
        )
        mc = info.get("marketCap")
        # yfinance reports debtToEquity in percentage points (e.g. 74.0 = 0.74x).
        de = info.get("debtToEquity")
        return {
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": mc / 1e6 if isinstance(mc, (int, float)) else None,  # $ millions
            "pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "ps": info.get("priceToSalesTrailing12Months"),
            "ev_sales": info.get("enterpriseToRevenue"),
            "gross_margin": pct("grossMargins"),
            "operating_margin": pct("operatingMargins"),
            "net_margin": pct("profitMargins"),
            "revenue_growth_yoy": pct("revenueGrowth"),
            "eps_growth_yoy": pct("earningsGrowth"),
            "fcf": fcf / 1e6 if isinstance(fcf, (int, float)) else None,  # $ millions
            "fcf_margin": fcf_margin,
            "roe": pct("returnOnEquity"),
            "debt_to_equity": round(de / 100, 2) if isinstance(de, (int, float)) else None,
            "current_ratio": info.get("currentRatio"),
            "beta": info.get("beta"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }

    def gross_margin_trend(self, symbol: str) -> dict | None:
        """Multi-year gross-margin path — the moat-durability tell. Stable/rising
        GM = pricing power; eroding GM = commoditization. Drilldown only (extra
        network call), so kept off the fast board scan."""
        try:
            import math

            import yfinance as yf

            fin = yf.Ticker(symbol).income_stmt
            if fin is None or fin.empty:
                return None
            gp = fin.loc["Gross Profit"] if "Gross Profit" in fin.index else None
            rev = fin.loc["Total Revenue"] if "Total Revenue" in fin.index else None
            if gp is None or rev is None:
                return None
            series = []
            for col in fin.columns:
                g, r = gp.get(col), rev.get(col)
                # NaN is truthy in Python — guard it so a missing year cannot
                # inject nan% and mislabel the trend direction.
                if g is None or r is None or math.isnan(g) or math.isnan(r) or r == 0:
                    continue
                series.append((str(col)[:4], round(g / r * 100, 1)))
            series = series[:4]  # newest-first, cap at 4 years
        except Exception as exc:
            log.warning("Yahoo margin trend failed for %s: %s", symbol, exc)
            return None
        if len(series) < 2:
            return None
        newest, oldest = series[0][1], series[-1][1]
        delta = round(newest - oldest, 1)
        direction = "rising" if delta > 1.5 else "eroding" if delta < -1.5 else "stable"
        return {"history": series, "delta_pts": delta, "direction": direction}


yahoo = YahooClient()
