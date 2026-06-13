"""Growth & Value scorecards across a dedicated ticker universe.

Long-horizon research lens (distinct from the short-term options scoring in
``scoring.py``). Two deterministic 0..100 scores per ticker, each built from
fundamentals via the providers. Each factor maps a metric to 0..10; weights sum
to 100. Missing metrics are scored N/A and the remaining weights re-normalize,
so thin-data tickers still land on a comparable 0..100 scale.

Two fingerprints by design:
  * Growth/Moat — gross-margin level (pricing power) + FCF margin (cash
    conversion, anti-dilution) on top of revenue/EPS growth. A no-margin
    revenue-grower (growth trap) scores low here.
  * Value — EV/Sales leads so a cyclical at a trough (depressed/negative EPS,
    P/E meaningless — the SanDisk-trough pattern) still scores; P/E de-weighted.

Yahoo (yfinance) is the primary fundamentals source (gross margin, FCF, EV/Sales,
D/E, forward P/E in one call); Alpha Vantage / Finnhub backfill gaps. The
per-ticker drilldown adds a multi-year gross-margin trend (moat-durability tell).

Board mechanics (cache + async refresh) mirror ``momentum.py``. Research only —
not investment advice.
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .models import GrowthValueItem
from .providers.alphavantage import alphavantage
from .providers.finnhub import finnhub
from .providers.mock import mock
from .providers.yahoo import yahoo

log = logging.getLogger(__name__)
settings = get_settings()


# --------------------------------------------------------------------------- #
# Scoring                                                                      #
# --------------------------------------------------------------------------- #
def _lerp(v: float, x0: float, y0: float, x1: float, y1: float) -> float:
    if x1 == x0:
        return y0
    return y0 + (v - x0) / (x1 - x0) * (y1 - y0)


def _band(v: float | None, lo: float, mid: float, hi: float) -> float | None:
    """Piecewise-linear 0..10, ascending: lo->0, mid->5, hi->10 (clamped)."""
    if v is None:
        return None
    if v <= lo:
        return 0.0
    if v >= hi:
        return 10.0
    return _lerp(v, lo, 0, mid, 5) if v <= mid else _lerp(v, mid, 5, hi, 10)


def _band_desc(v: float | None, lo: float, mid: float, hi: float) -> float | None:
    """Lower-is-better: lo->10, mid->5, hi->0."""
    b = _band(v, lo, mid, hi)
    return None if b is None else 10.0 - b


def _assemble(rows: list[tuple]) -> dict:
    """rows: (key, label, raw_value, points|None). Re-normalize over present
    factors so a 0..100 score is comparable regardless of data coverage."""
    factors, acc, total_w = [], 0.0, 0.0
    for key, label, value, points, weight in rows:
        factors.append({
            "key": key,
            "label": label,
            "value": value,
            "points": round(points, 1) if points is not None else None,
            "weight": weight,
            "max": 10,
        })
        if points is not None:
            acc += points / 10 * weight
            total_w += weight
    score = round(acc / total_w * 100) if total_w else 0
    return {"score": score, "factors": factors, "coverage_pct": round(total_w)}


def compute_growth_score(m: dict | None) -> dict:
    """0..100 growth + moat-quality score with per-factor breakdown.

    Beyond raw growth this fingerprints the *durable-compounder* (NVDA-pattern):
    high gross margin = pricing power, FCF margin = cash conversion not dilution.
    A no-margin revenue-grower (the growth trap) scores low here by design."""
    m = m or {}
    rev = m.get("revenue_growth_yoy")
    eps = m.get("eps_growth_yoy")
    gm = m.get("gross_margin")
    fcfm = m.get("fcf_margin")
    roe = m.get("roe")
    opm = m.get("operating_margin")
    pe = m.get("pe")

    # PEG-like valuation discipline: cheap relative to its own growth.
    if pe is None or eps is None:
        peg, peg_pts = None, None
    elif pe <= 0 or eps <= 0:
        peg, peg_pts = None, 0.0  # no earnings or no growth -> undisciplined
    else:
        peg = round(pe / eps, 2)
        peg_pts = _band_desc(peg, 1, 2, 4)

    return _assemble([
        ("revenue_growth", "Revenue growth (YoY %)", rev, _band(rev, 0, 10, 40), 20),
        ("eps_growth", "EPS growth (YoY %)", eps, _band(eps, 0, 10, 40), 15),
        ("gross_margin", "Pricing power (gross margin %)", gm, _band(gm, 20, 45, 70), 20),
        ("fcf_margin", "Cash conversion (FCF margin %)", fcfm, _band(fcfm, 0, 10, 25), 15),
        ("operating_margin", "Operating margin (%)", opm, _band(opm, 0, 15, 30), 10),
        ("roe", "Return on equity (%)", roe, _band(roe, 0, 15, 30), 10),
        ("peg", "Valuation discipline (PEG)", peg, peg_pts, 10),
    ])


def compute_value_score(m: dict | None) -> dict:
    """0..100 value score with per-factor breakdown.

    Cyclical-safe: EV/Sales is the lead cheapness factor because it stays valid
    at a cycle trough when EPS is depressed/negative and P/E goes meaningless
    (the SanDisk-trough pattern). P/E is kept but de-weighted for that reason."""
    m = m or {}
    pe = m.get("pe")
    ps = m.get("ps")
    evs = m.get("ev_sales")
    dte = m.get("debt_to_equity")
    cr = m.get("current_ratio")
    roe = m.get("roe")
    nm = m.get("net_margin")
    price = m.get("price")
    hi = m.get("52w_high")
    lo = m.get("52w_low")

    evs_pts = None if (evs is None or evs <= 0) else _band_desc(evs, 0.5, 3, 8)
    pe_pts = None if pe is None else (0.0 if pe <= 0 else _band_desc(pe, 8, 15, 30))
    ps_pts = None if (ps is None or ps <= 0) else _band_desc(ps, 1, 4, 10)
    dte_pts = None if dte is None else (0.0 if dte < 0 else _band_desc(dte, 0.3, 1, 2.5))

    # Mean-reversion: where price sits in its 52-week range (near low = cheaper).
    pos, pos_pts = None, None
    if price is not None and hi is not None and lo is not None and hi > lo:
        pos = round((price - lo) / (hi - lo), 2)
        pos_pts = _band_desc(pos, 0, 0.5, 1)

    return _assemble([
        ("ev_sales", "Cyclical-safe cheapness (EV/Sales)", evs, evs_pts, 20),
        ("pe", "Earnings cheapness (P/E)", pe, pe_pts, 15),
        ("ps", "Sales cheapness (P/S)", ps, ps_pts, 10),
        ("debt_to_equity", "Balance-sheet safety (D/E)", dte, dte_pts, 15),
        ("roe", "Quality at price (ROE %)", roe, _band(roe, 0, 15, 30), 10),
        ("current_ratio", "Liquidity (current ratio)", cr, _band(cr, 1, 1.5, 2.5), 5),
        ("net_margin", "Profitability (net margin %)", nm, _band(nm, 0, 15, 30), 10),
        ("mean_reversion", "52-week range position", pos, pos_pts, 15),
    ])


# --------------------------------------------------------------------------- #
# Entry guidance — deterministic, hedged. NEVER a buy signal.                  #
# --------------------------------------------------------------------------- #
def entry_guidance(m: dict, growth: dict, value: dict, margin_trend: dict | None) -> dict:
    """Data-derived flags + things to watch. Mirrors the alert engine's
    reasons/risks/invalidation discipline: observations, not recommendations.
    There is no 'safe' price — these only surface what a disciplined investor
    would verify and monitor before and after initiating."""
    g, v = growth.get("score", 0), value.get("score", 0)
    pe, fpe = m.get("pe"), m.get("forward_pe")
    dte, fcfm = m.get("debt_to_equity"), m.get("fcf_margin")
    price, hi, lo = m.get("price"), m.get("52w_high"), m.get("52w_low")

    pos = None
    if price is not None and hi is not None and lo is not None and hi > lo:
        pos = (price - lo) / (hi - lo)

    # Valuation state (cheap/fair/rich × where in the 52-week range).
    cheap = "screens cheap" if v >= 60 else "screens rich" if v <= 40 else "fairly valued"
    where = (
        "near 52-week high" if pos is not None and pos > 0.75
        else "near 52-week low" if pos is not None and pos < 0.35
        else "mid-range"
    )
    valuation_state = f"{cheap} · {where}" if pos is not None else cheap

    flags: list[dict] = []
    # The headline cyclical trap: cheap forward P/E + price near the high.
    if pe and fpe and pe > 0 and fpe > 0 and fpe / pe < 0.65 and (pos or 0) > 0.7:
        flags.append({"level": "flag", "text": (
            f"Possible cycle peak: forward P/E ({round(fpe,1)}) sits far below trailing "
            f"({round(pe,1)}) while price is near its 52-week high. The forward multiple "
            "may be flattered by peak-cycle earnings — verify against normalized / mid-cycle "
            "earnings before reading it as 'cheap'."
        )})
    if margin_trend and margin_trend.get("direction") == "eroding":
        flags.append({"level": "flag", "text": (
            f"Gross margin eroding ({margin_trend['delta_pts']} pts over the window) — "
            "pricing power may be weakening (commoditization risk). The moat fingerprint is fading."
        )})
    if fcfm is not None and fcfm <= 0:
        flags.append({"level": "caution", "text": (
            "Not self-funding: free-cash-flow margin is negative. Growth depends on external "
            "capital — watch for dilution or rising debt."
        )})
    if dte is not None and dte > 2:
        flags.append({"level": "caution", "text": (
            f"High leverage (D/E {dte}) — thinner cushion through a downturn or rate shock."
        )})
    if g >= 70 and v <= 40:
        flags.append({"level": "note", "text": (
            "High quality, richly priced: returns now lean on growth being delivered and the "
            "multiple not compressing. Little margin of safety in price — for names like this the "
            "usual entry is a thesis-intact drawdown, not a discount."
        )})
    if v >= 65 and g <= 35:
        flags.append({"level": "note", "text": (
            "Cheap but low-quality on these metrics — confirm it's a cyclical trough / temporary "
            "depression, not secular decline (the value-trap test)."
        )})

    watch = [
        "Gross-margin trend each quarter — rising/stable = moat intact; falling = thesis cracking.",
        "Revenue growth: re-accelerating or decelerating? Acceleration is the inflection signal.",
        "Free-cash-flow margin direction (cash conversion, not just reported earnings).",
        "Whether the cheapness is on normalized earnings or peak-cycle earnings.",
    ]
    return {
        "valuation_state": valuation_state,
        "flags": flags,
        "watch": watch,
        "disclaimer": (
            "No 'safe' price exists. These are research observations, not a recommendation to "
            "buy or sell. Size positions so being wrong isn't fatal; exit on thesis-loss (the "
            "signals break), not price-loss (it merely fell)."
        ),
    }


# --------------------------------------------------------------------------- #
# Data fetch                                                                   #
# --------------------------------------------------------------------------- #
def _fetch_metrics(symbol: str) -> dict | None:
    """Fundamentals merged across providers + a current price for mean-reversion.

    Yahoo (yfinance) is the primary source: one call returns the moat/cyclical
    fingerprint fields Alpha Vantage OVERVIEW lacks — gross margin, FCF margin,
    EV/Sales, D/E, forward P/E. Alpha Vantage / Finnhub then *fill* any gaps
    (they never overwrite a present yfinance value).
    """
    if settings.use_mock_data:
        m = mock.get_metrics(symbol) if hasattr(mock, "get_metrics") else None
        m = dict(m or {})
        q = mock.get_quote(symbol)
        if q:
            m.setdefault("price", q.get("last"))
        return m or None

    yf = yahoo.get_fundamentals(symbol)
    av = alphavantage.get_metrics(symbol) if alphavantage.configured else None
    fh = finnhub.get_metrics(symbol) if finnhub.configured else None
    if not yf and not av and not fh:
        return None
    # yfinance is primary; backfill missing fields from AV then Finnhub.
    m: dict = dict(yf or {})
    for src in (av, fh):
        for k, v in (src or {}).items():
            if v is not None and m.get(k) is None:
                m[k] = v

    # Ensure a current price for the 52-week mean-reversion factor.
    if m.get("price") is None:
        q = (
            (finnhub.get_quote(symbol) if finnhub.configured else None)
            or yahoo.get_quote(symbol)
            or (alphavantage.get_quote(symbol) if alphavantage.configured else None)
        )
        if q:
            m["price"] = q.get("last")
    return m


def _load_note(symbol: str) -> dict | None:
    """Stored human moat thesis for a ticker, if any."""
    from .models import GrowthValueNote

    with SessionLocal() as db:
        n = db.scalar(select(GrowthValueNote).where(GrowthValueNote.symbol == symbol.upper()))
        if not n:
            return None
        return {
            "thesis": n.thesis,
            "risks": n.risks,
            "watch": n.watch,
            "updated_at": n.updated_at.isoformat() if n.updated_at else None,
        }


def scorecard(symbol: str) -> dict:
    """Full per-ticker payload: both scores with factor breakdowns + raw metrics."""
    symbol = symbol.upper()
    m = _fetch_metrics(symbol)
    if not m:
        return {
            "symbol": symbol,
            "available": False,
            "unavailable_reason": "No fundamentals available for this ticker from configured providers.",
            "growth": compute_growth_score(None),
            "value": compute_value_score(None),
            "note": _load_note(symbol),
            "metrics": {},
        }
    growth = compute_growth_score(m)
    value = compute_value_score(m)
    margin_trend = yahoo.gross_margin_trend(symbol) if not settings.use_mock_data else None
    return {
        "symbol": symbol,
        "available": True,
        "growth": growth,
        "value": value,
        "margin_trend": margin_trend,
        "entry_guidance": entry_guidance(m, growth, value, margin_trend),
        "note": _load_note(symbol),
        "metrics": {
            "price": m.get("price"),
            "market_cap": m.get("market_cap"),
            "pe": m.get("pe"),
            "forward_pe": m.get("forward_pe"),
            "ps": m.get("ps"),
            "ev_sales": m.get("ev_sales"),
            "revenue_growth_yoy": m.get("revenue_growth_yoy"),
            "eps_growth_yoy": m.get("eps_growth_yoy"),
            "gross_margin": m.get("gross_margin"),
            "net_margin": m.get("net_margin"),
            "operating_margin": m.get("operating_margin"),
            "fcf_margin": m.get("fcf_margin"),
            "roe": m.get("roe"),
            "debt_to_equity": m.get("debt_to_equity"),
            "current_ratio": m.get("current_ratio"),
            "beta": m.get("beta"),
            "52w_high": m.get("52w_high"),
            "52w_low": m.get("52w_low"),
            "sector": m.get("sector"),
            "industry": m.get("industry"),
        },
    }


# --------------------------------------------------------------------------- #
# Board (cache + async refresh) — mirrors momentum.py                          #
# --------------------------------------------------------------------------- #
_lock = threading.Lock()
_cache: dict = {"updated_at": None, "scanning": False, "results": [], "pending": False}


def universe() -> list[str]:
    """Growth/Value-list tickers only — no fallback (this board has its own list)."""
    with SessionLocal() as db:
        return sorted(
            db.scalars(select(GrowthValueItem.symbol).where(GrowthValueItem.enabled.is_(True))).all()
        )


def _scan_one(symbol: str) -> dict | None:
    try:
        m = _fetch_metrics(symbol)
    except Exception:
        log.exception("Growth/Value scan failed for %s", symbol)
        return None
    if not m:
        return None
    g = compute_growth_score(m)
    v = compute_value_score(m)
    return {
        "symbol": symbol,
        "growth_score": g["score"],
        "value_score": v["score"],
        "price": m.get("price"),
        "market_cap": m.get("market_cap"),
        "pe": m.get("pe"),
        "ps": m.get("ps"),
        "ev_sales": m.get("ev_sales"),
        "revenue_growth_yoy": m.get("revenue_growth_yoy"),
        "eps_growth_yoy": m.get("eps_growth_yoy"),
        "gross_margin": m.get("gross_margin"),
        "net_margin": m.get("net_margin"),
        "fcf_margin": m.get("fcf_margin"),
        "roe": m.get("roe"),
        "debt_to_equity": m.get("debt_to_equity"),
    }


def refresh(max_workers: int = 2) -> None:
    """Scan the universe and update the cache. Two workers keeps Alpha Vantage
    under its 75 req/min ceiling (~2-3 calls per ticker)."""
    with _lock:
        if _cache["scanning"]:
            _cache["pending"] = True
            return
        _cache["scanning"] = True
    try:
        results: list[dict] = []
        symbols = universe()
        if symbols:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_scan_one, s): s for s in symbols}
                for fut in as_completed(futures):
                    row = fut.result()
                    if row:
                        results.append(row)
        results.sort(key=lambda r: r["growth_score"], reverse=True)
        with _lock:
            _cache["results"] = results
            _cache["updated_at"] = datetime.now(timezone.utc).isoformat()
        log.info("Growth/Value scan complete: %d tickers scored", len(results))
    finally:
        with _lock:
            _cache["scanning"] = False
            rerun = _cache["pending"]
            _cache["pending"] = False
        if rerun:
            threading.Thread(target=refresh, daemon=True).start()


def refresh_async() -> bool:
    """Kick a refresh in a daemon thread; queue a trailing run if one is active."""
    with _lock:
        if _cache["scanning"]:
            _cache["pending"] = True
            return False
    threading.Thread(target=refresh, daemon=True).start()
    return True


def snapshot(limit: int = 50, sort_by: str = "growth") -> dict:
    """Cached scores filtered to the *current* universe (removed tickers vanish
    immediately). sort_by: 'growth' or 'value'."""
    allowed = set(universe())
    key = "value_score" if sort_by == "value" else "growth_score"
    with _lock:
        rows = [r for r in _cache["results"] if r["symbol"] in allowed]
        rows = sorted(rows, key=lambda r: r.get(key, 0), reverse=True)
        return {
            "updated_at": _cache["updated_at"],
            "scanning": _cache["scanning"],
            "sort_by": "value" if sort_by == "value" else "growth",
            "results": rows[:limit],
        }
