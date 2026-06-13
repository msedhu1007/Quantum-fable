"""Scanner — gathers data per ticker, scores it, persists snapshots, fires alerts."""
import logging
from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import alerts as alert_service
from . import analyst
from . import technicals
from .config import get_settings
from .db import SessionLocal
from .models import Alert, ModelDecision, NewsItem, OptionsSnapshot, TickerSnapshot, WatchlistItem
from .providers.alphavantage import alphavantage
from .providers.benzinga import benzinga
from .providers.finnhub import finnhub
from .providers.mock import mock
from .providers.polygon import polygon
from .providers.yahoo import yahoo
from .providers.tradier import tradier
from .scoring import _dte, find_best_contract, make_alert, rate_fundamentals, score_signal

log = logging.getLogger(__name__)
settings = get_settings()

EASTERN = ZoneInfo("America/New_York")


def market_provider():
    """Quotes/history/options source — mock when forced, else Tradier, else Polygon."""
    if settings.use_mock_data:
        return mock
    return tradier if tradier.configured else polygon


def market_is_open(now: datetime | None = None) -> bool:
    now = now or datetime.now(EASTERN)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes <= 16 * 60


def _indicators(symbol: str, history_days: int = 320) -> dict:
    """Live price + full technical indicator suite from daily history."""
    out: dict = {}
    provider = market_provider()

    # Price: freshest of Finnhub (real-time in-session but frozen at the close —
    # free tier has no after-hours), Yahoo (real-time extended hours, keyless),
    # Polygon options-underlying (15-min delayed). Fallbacks: Alpha Vantage → provider.
    quote = None
    if not settings.use_mock_data:
        candidates = []
        if finnhub.configured:
            fq = finnhub.get_quote(symbol)
            if fq:
                candidates.append(fq)
        # Finnhub fresh → done. Stale/missing → ask the extended-hours sources too.
        fq_age = None
        if candidates and candidates[0].get("quote_time"):
            fq_age = datetime.now(timezone.utc).timestamp() - candidates[0]["quote_time"]
        if not candidates or fq_age is None or fq_age > 20 * 60:
            yq = yahoo.get_quote(symbol)
            if yq:
                candidates.append(yq)
            if polygon.configured:
                pq = polygon.get_underlying_price(symbol)
                if pq:
                    candidates.append(pq)
        if candidates:
            quote = max(candidates, key=lambda q: q.get("quote_time") or 0)
    quote = (
        quote
        or (alphavantage.get_quote(symbol) if alphavantage.configured and not settings.use_mock_data else None)
        or provider.get_quote(symbol)
    )
    if not quote:
        return out
    out["price"] = quote.get("last")
    out["volume"] = quote.get("volume")
    out["change_pct"] = quote.get("change_percentage")
    out["price_stale"] = quote.get("stale", False)

    today = date.today()
    start, end = (today - timedelta(days=history_days)).isoformat(), today.isoformat()
    # Daily history: AV when configured (Polygon stock endpoints are rate-limited on options plans)
    history = (
        alphavantage.get_daily_history(symbol, start, end)
        if alphavantage.configured and not settings.use_mock_data
        else []
    ) or provider.get_daily_history(symbol, start, end)
    out.update(technicals.compute(history, live_price=out["price"]))

    # Fill daily change % when the price source didn't supply it (Polygon underlying)
    if out.get("change_pct") is None and out.get("price") and len(history) >= 1:
        prev_close = history[-1].get("close")
        if prev_close:
            out["change_pct"] = round((out["price"] - prev_close) / prev_close * 100, 2)

    # Legacy keys the frontend and market-trend logic rely on
    if out.get("sma_20") is not None:
        out["dma_20"] = out["sma_20"]
        if out["price"] is not None:
            out["price_above_20dma"] = out["price"] > out["sma_20"]
            out["price_below_20dma"] = out["price"] < out["sma_20"]

    # Recent closes for the frontend sparkline (small payload, ~60 points)
    closes = [d["close"] for d in history if d.get("close") is not None]
    if closes:
        out["history_closes"] = [round(c, 2) for c in closes[-60:]]

    volumes = [d["volume"] for d in history if d.get("volume") is not None]
    if volumes:
        if out.get("volume") is None:  # Finnhub quote carries no volume
            out["volume"] = volumes[-1]
        avg_vol = sum(volumes[-20:]) / min(len(volumes), 20)
        if avg_vol > 0 and out["volume"]:
            out["relative_volume"] = round(out["volume"] / avg_vol, 2)
    return out


def _options_metrics(symbol: str) -> dict:
    """Aggregate call/put flow across 7-45 DTE expirations and pick best contracts."""
    out: dict = {"call_volume": 0, "put_volume": 0, "best_call": None, "best_put": None}
    provider = market_provider()
    expirations = [
        e for e in provider.get_expirations(symbol)
        if settings.min_dte <= _dte(e) <= settings.max_dte
    ][:3]  # cap API calls per ticker

    all_options: list[dict] = []
    ivs: list[float] = []
    for exp in expirations:
        chain = provider.get_chain(symbol, exp)
        all_options.extend(chain)
        for o in chain:
            if o.get("option_type") == "call":
                out["call_volume"] += o.get("volume") or 0
            elif o.get("option_type") == "put":
                out["put_volume"] += o.get("volume") or 0
            iv = (o.get("greeks") or {}).get("mid_iv")
            if iv:
                ivs.append(iv)

    if out["put_volume"]:
        out["call_volume_ratio"] = round(out["call_volume"] / out["put_volume"], 2)
    if out["call_volume"]:
        out["put_volume_ratio"] = round(out["put_volume"] / out["call_volume"], 2)
    if ivs:
        out["chain_mean_iv"] = round(sum(ivs) / len(ivs), 4)

    out["best_call"] = find_best_contract(all_options, "call")
    out["best_put"] = find_best_contract(all_options, "put")
    return out


def _trend_of(symbol: str) -> int:
    """+1 above 20-DMA, -1 below, 0 unknown. Short history window — trend only."""
    try:
        ind = _indicators(symbol, history_days=60)
    except Exception:
        log.exception("Failed to fetch trend for %s", symbol)
        return 0
    if ind.get("price_above_20dma"):
        return 1
    if ind.get("price_below_20dma"):
        return -1
    return 0


def _market_trend() -> str:
    """SPY + QQQ vs their 20-day moving averages → bullish / bearish / neutral."""
    total = _trend_of(settings.market_benchmark) + _trend_of("QQQ")
    if total >= 2:
        return "bullish"
    if total <= -2:
        return "bearish"
    return "neutral"


def gather_ticker_data(symbol: str, market_trend: str | None = None) -> dict:
    """Assemble the full input dict for scoring + research view.
    Independent provider calls run in parallel — biggest research-page speedup."""
    data: dict = {"ticker": symbol}
    futures: dict = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures["indicators"] = pool.submit(_indicators, symbol)
        futures["options"] = pool.submit(_options_metrics, symbol)
        if market_trend is None:
            futures["trend"] = pool.submit(_market_trend)
        if not settings.use_mock_data and alphavantage.configured:
            futures["fundamentals"] = pool.submit(alphavantage.get_metrics, symbol)
            futures["sentiment"] = pool.submit(alphavantage.news_sentiment, symbol)
            futures["av_news"] = pool.submit(alphavantage.company_news, symbol)
            futures["earnings"] = pool.submit(alphavantage.next_earnings, symbol)
        if not settings.use_mock_data and benzinga.configured:
            futures["bz_news"] = pool.submit(benzinga.company_news, symbol)

    def result(key, default=None):
        fut = futures.get(key)
        if fut is None:
            return default
        try:
            return fut.result()
        except Exception:
            log.exception("gather: %s failed for %s", key, symbol)
            return default

    data.update(result("indicators", {}) or {})
    data.update(result("options", {}) or {})
    data["market_trend"] = market_trend or result("trend", "neutral")

    if settings.use_mock_data:
        # Synthetic sentiment so BULL/BEAR exercise the full alert path keylessly
        data.setdefault("news_sentiment", {"BULL": 0.8, "BEAR": -0.8}.get(symbol, 0.0))
        return data

    news: list[dict] = []
    if alphavantage.configured:
        data["fundamentals"] = result("fundamentals")
        data["news_sentiment"] = result("sentiment")
        news.extend(result("av_news", []) or [])
        earnings = result("earnings")
        if earnings and earnings.get("date"):
            data["next_earnings_date"] = earnings["date"]
    if finnhub.configured:
        if data.get("fundamentals") is None:
            data["fundamentals"] = finnhub.get_metrics(symbol)
        if data.get("news_sentiment") is None:
            data["news_sentiment"] = finnhub.news_sentiment(symbol)
        if not news:
            news.extend(
                {
                    "headline": n.get("headline"),
                    "source": n.get("source"),
                    "url": n.get("url"),
                    "datetime": n.get("datetime"),
                }
                for n in finnhub.company_news(symbol)[:10]
            )
        if "next_earnings_date" not in data:
            earnings = finnhub.next_earnings(symbol)
            if earnings:
                data["next_earnings_date"] = earnings.get("date")
    if data.get("fundamentals") is not None:
        data["fundamental_rating"] = rate_fundamentals(data["fundamentals"])
    if benzinga.configured:
        seen_urls = {n["url"] for n in news if n.get("url")}
        news.extend(n for n in benzinga.company_news(symbol) if n.get("url") not in seen_urls)
    if news:
        data["news"] = sorted(news, key=lambda n: n.get("datetime") or 0, reverse=True)[:15]
    return data


def scan_ticker(symbol: str, db: Session, market_trend: str | None = None) -> dict:
    """Scan one ticker: gather → score → persist → (maybe) alert. Returns the alert dict."""
    symbol = symbol.upper()
    data = gather_ticker_data(symbol, market_trend)
    score = score_signal(data)
    result = make_alert(symbol, score, data.get("best_call"), data.get("best_put"))

    # Persist snapshots
    db.add(TickerSnapshot(
        symbol=symbol,
        price=data.get("price"),
        volume=data.get("volume"),
        relative_volume=data.get("relative_volume"),
        dma_20=data.get("dma_20"),
        data={k: v for k, v in data.items() if k not in ("news",)},
    ))
    db.add(OptionsSnapshot(
        symbol=symbol,
        call_volume=data.get("call_volume"),
        put_volume=data.get("put_volume"),
        best_call=data.get("best_call"),
        best_put=data.get("best_put"),
    ))
    for n in data.get("news") or []:
        if n.get("headline"):
            db.add(NewsItem(symbol=symbol, headline=n["headline"], source=n.get("source"), url=n.get("url")))

    # Optional LLM explanation layer for qualifying setups
    if result["decision"] != "NO TRADE" and analyst.enabled():
        llm = analyst.analyze({**data, "engine_score": score, "engine_decision": result["decision"],
                               "candidate_contract": result["contract"]})
        if llm:
            db.add(ModelDecision(symbol=symbol, model=settings.anthropic_model,
                                 input_summary={"score": score}, output=llm))
            # LLM may only downgrade to NO TRADE, never flip direction
            if llm["decision"] in (result["decision"], "NO TRADE"):
                result["decision"] = llm["decision"]
            result["confidence"] = llm.get("confidence")
            result["reasons"] = llm.get("reasons")
            result["risks"] = llm.get("risks")
            result["invalidation_level"] = llm.get("invalidation_level")
            if llm.get("alert_message"):
                result["message"] = llm["alert_message"]

    record = Alert(
        symbol=symbol,
        decision=result["decision"],
        score=result["score"],
        confidence=result.get("confidence"),
        contract=result.get("contract"),
        reasons=result.get("reasons"),
        risks=result.get("risks"),
        invalidation_level=result.get("invalidation_level"),
        message=result.get("message"),
    )
    db.add(record)
    db.commit()

    if result["decision"] in ("CALL", "PUT"):
        if _recently_alerted(db, symbol, result["decision"], exclude_id=record.id):
            log.info("Dedup: %s %s alerted within last %s min — not re-dispatching",
                     symbol, result["decision"], settings.alert_cooldown_minutes)
        else:
            record.dispatched = alert_service.dispatch(result)
            db.commit()

    return result


def _recently_alerted(db: Session, symbol: str, decision: str, exclude_id: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.alert_cooldown_minutes)
    return db.scalars(
        select(Alert.id)
        .where(
            Alert.symbol == symbol,
            Alert.decision == decision,
            Alert.dispatched.is_(True),
            Alert.created_at >= cutoff,
            Alert.id != exclude_id,
        )
        .limit(1)
    ).first() is not None


# Last-scan stats for the dashboard scanner card (in-process, reset on restart)
scan_status: dict = {
    "last_scan_at": None,
    "scanned": 0,
    "calls": 0,
    "puts": 0,
    "no_trades": 0,
    "skipped_reason": None,
}


def scan_all() -> list[dict]:
    """Scheduler entrypoint — scan every enabled watchlist symbol."""
    if settings.market_hours_only and not market_is_open():
        log.info("Market closed — skipping scan")
        scan_status["skipped_reason"] = "market closed"
        return []
    if not market_provider().configured:
        log.warning("No market data provider configured (TRADIER_API_KEY or POLYGON_API_KEY) — skipping scan")
        scan_status["skipped_reason"] = "no market data provider"
        return []

    results = []
    with SessionLocal() as db:
        symbols = db.scalars(
            select(WatchlistItem.symbol).where(WatchlistItem.enabled.is_(True))
        ).all()
        trend = _market_trend()
        for symbol in symbols:
            try:
                results.append(scan_ticker(symbol, db, market_trend=trend))
            except Exception:
                log.exception("Scan failed for %s", symbol)

    decisions = [r["decision"] for r in results]
    scan_status.update({
        "last_scan_at": datetime.now(timezone.utc).isoformat(),
        "scanned": len(results),
        "calls": decisions.count("CALL"),
        "puts": decisions.count("PUT"),
        "no_trades": decisions.count("NO TRADE"),
        "skipped_reason": None,
    })
    return results
