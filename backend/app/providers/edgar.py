"""SEC EDGAR insider-trading client (Form 4) — keyless, official source.

Form 4 = corporate insiders (officers, directors, 10% owners) reporting buys and
sells, due within 2 business days of the trade. Flow: full-text search for recent
Form 4 filings mentioning the ticker → fetch each XML → parse open-market
transactions (code P = purchase, S = sale). Results cached per ticker for an hour;
SEC fair-access rules want a descriptive User-Agent and gentle request rates.
"""
import logging
import threading
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import httpx

log = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "QuantumFable options research msedhu@gmail.com"}
_CACHE_TTL = 3600.0
_MAX_FILINGS = 8

_client = httpx.Client(headers=_HEADERS, timeout=20.0, follow_redirects=True)
_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


def _text(el, path) -> str | None:
    node = el.find(path)
    return node.text.strip() if node is not None and node.text else None


def _parse_form4(xml_text: str, symbol: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    if (_text(root, ".//issuerTradingSymbol") or "").upper() != symbol:
        return []  # filing only mentioned the ticker, different issuer

    owner = _text(root, ".//reportingOwner/reportingOwnerId/rptOwnerName")
    rel = root.find(".//reportingOwner/reportingOwnerRelationship")
    role = None
    if rel is not None:
        if _text(rel, "officerTitle"):
            role = _text(rel, "officerTitle")
        elif _text(rel, "isDirector") == "1":
            role = "Director"
        elif _text(rel, "isTenPercentOwner") == "1":
            role = "10% owner"

    out = []
    for txn in root.findall(".//nonDerivativeTransaction"):
        code = _text(txn, ".//transactionCoding/transactionCode")
        if code not in ("P", "S"):  # open-market purchase / sale only
            continue
        shares = _text(txn, ".//transactionAmounts/transactionShares/value")
        price = _text(txn, ".//transactionAmounts/transactionPricePerShare/value")
        out.append({
            "name": owner,
            "role": role,
            "type": "BUY" if code == "P" else "SELL",
            "date": _text(txn, ".//transactionDate/value"),
            "shares": float(shares) if shares else None,
            "price": float(price) if price else None,
            "value": round(float(shares) * float(price)) if shares and price else None,
        })
    return out


def insider_summary(symbol: str, days_back: int = 90) -> dict | None:
    """Recent open-market insider buys/sells for a ticker, or None on failure."""
    symbol = symbol.upper()
    with _lock:
        hit = _cache.get(symbol)
        if hit and time.monotonic() - hit[0] < _CACHE_TTL:
            return hit[1]
    try:
        search = _client.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={
                "q": f'"{symbol}"',
                "forms": "4",
                "dateRange": "custom",
                "startdt": (date.today() - timedelta(days=days_back)).isoformat(),
                "enddt": date.today().isoformat(),
            },
        )
        search.raise_for_status()
        hits = (search.json().get("hits") or {}).get("hits") or []
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("EDGAR search failed for %s: %s", symbol, exc)
        return None

    transactions: list[dict] = []
    for hit in hits[:_MAX_FILINGS]:
        try:
            accession, filename = hit["_id"].split(":", 1)
            cik = (hit["_source"].get("ciks") or [None])[0]
            if not cik:
                continue
            url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{accession.replace('-', '')}/{filename}"
            )
            resp = _client.get(url)
            resp.raise_for_status()
            transactions.extend(_parse_form4(resp.text, symbol))
            time.sleep(0.15)  # stay well under SEC's 10 req/s ceiling
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            log.debug("EDGAR filing fetch failed: %s", exc)

    transactions.sort(key=lambda t: t.get("date") or "", reverse=True)
    buys = [t for t in transactions if t["type"] == "BUY"]
    sells = [t for t in transactions if t["type"] == "SELL"]
    summary = {
        "buys": len(buys),
        "sells": len(sells),
        "buy_value": sum(t["value"] or 0 for t in buys),
        "sell_value": sum(t["value"] or 0 for t in sells),
        "recent": transactions[:10],
        "window_days": days_back,
        "source": "SEC EDGAR Form 4",
    }
    with _lock:
        _cache[symbol] = (time.monotonic(), summary)
    return summary


