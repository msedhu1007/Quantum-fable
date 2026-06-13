"""Technical indicators computed from daily OHLCV history.

Pure functions over a list of daily bars (oldest → newest). Bars need at least
"close"; "high"/"low"/"open"/"volume" are used when present. All computation is
deterministic — this module feeds scoring.score_signal(), it never decides alone.
"""
from statistics import pstdev


def sma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def ema(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    value = sum(closes[:period]) / period
    for close in closes[period:]:
        value = close * k + value * (1 - k)
    return value


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for prev, cur in zip(closes[:-1], closes[1:]):
        change = cur - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def macd(closes: list[float]) -> dict | None:
    """MACD(12,26,9) — returns macd line, signal line, histogram."""
    if len(closes) < 26 + 9:
        return None
    macd_series = []
    for i in range(26, len(closes) + 1):
        window = closes[:i]
        macd_series.append(ema(window, 12) - ema(window, 26))
    signal = ema(macd_series, 9)
    if signal is None:
        return None
    line = macd_series[-1]
    return {"macd": line, "signal": signal, "histogram": line - signal}


def bollinger(closes: list[float], period: int = 20, mult: float = 2.0) -> dict | None:
    if len(closes) < period:
        return None
    mid = sma(closes, period)
    sd = pstdev(closes[-period:])
    return {"upper": mid + mult * sd, "middle": mid, "lower": mid - mult * sd}


def atr(bars: list[dict], period: int = 14) -> float | None:
    usable = [b for b in bars if b.get("high") is not None and b.get("low") is not None]
    if len(usable) < period + 1:
        return None
    trs = []
    for prev, cur in zip(usable[:-1], usable[1:]):
        prev_close = prev.get("close") or prev["low"]
        trs.append(max(
            cur["high"] - cur["low"],
            abs(cur["high"] - prev_close),
            abs(cur["low"] - prev_close),
        ))
    value = sum(trs[:period]) / period
    for tr in trs[period:]:
        value = (value * (period - 1) + tr) / period
    return value


def compute(bars: list[dict], live_price: float | None = None) -> dict:
    """All indicators + a five-level technical rating.

    bars: daily history oldest → newest. live_price overrides the last close as
    "current price" so intraday quotes sharpen the signal.
    """
    closes = [b["close"] for b in bars if b.get("close") is not None]
    if len(closes) < 21:
        return {}
    price = live_price or closes[-1]

    out: dict = {"price": price}
    for label, value in (
        ("ema_9", ema(closes, 9)),
        ("sma_20", sma(closes, 20)),
        ("sma_50", sma(closes, 50)),
        ("sma_200", sma(closes, 200)),
        ("rsi_14", rsi(closes)),
        ("atr_14", atr(bars)),
    ):
        if value is not None:
            out[label] = round(value, 2)
    m = macd(closes)
    if m:
        out["macd"] = {k: round(v, 4) for k, v in m.items()}
    bb = bollinger(closes)
    if bb:
        out["bollinger"] = {k: round(v, 2) for k, v in bb.items()}

    # Breakout / breakdown vs prior 20-day range (excluding today)
    prior = bars[:-1] if len(bars) > 1 else bars
    highs = [b.get("high") or b["close"] for b in prior[-20:] if b.get("close") is not None]
    lows = [b.get("low") or b["close"] for b in prior[-20:] if b.get("close") is not None]
    if highs and lows:
        out["high_20d"], out["low_20d"] = round(max(highs), 2), round(min(lows), 2)
        out["breakout"] = price > max(highs)
        out["breakdown"] = price < min(lows)

    # Gap vs previous close
    last_open, prev_close = bars[-1].get("open"), (bars[-2].get("close") if len(bars) >= 2 else None)
    if last_open and prev_close:
        gap_pct = (last_open - prev_close) / prev_close * 100
        out["gap_pct"] = round(gap_pct, 2)
        out["gap_up"], out["gap_down"] = gap_pct > 1.0, gap_pct < -1.0

    out["technical_rating"] = _rate(out, price)

    # --- Interpreted signals (pure derivations for analysis UI) ---

    # MA alignment
    ma_keys = ("ema_9", "sma_20", "sma_50", "sma_200")
    ma_vals = [(k, out[k]) for k in ma_keys if k in out]
    if ma_vals:
        above = sum(1 for _, v in ma_vals if price > v)
        vals = [v for _, v in ma_vals]
        if above == len(ma_vals) and vals == sorted(vals, reverse=True):
            out["ma_alignment"] = "bullish_stack"
        elif above == 0 and vals == sorted(vals):
            out["ma_alignment"] = "bearish_stack"
        elif above == len(ma_vals):
            out["ma_alignment"] = "bullish"
        elif above == 0:
            out["ma_alignment"] = "bearish"
        else:
            out["ma_alignment"] = "mixed"

    sma50 = out.get("sma_50")
    sma200 = out.get("sma_200")
    if sma50 is not None and sma200 is not None:
        out["golden_cross"] = sma50 > sma200
        out["death_cross"] = sma50 < sma200

    # RSI interpretation
    r = out.get("rsi_14")
    if r is not None:
        if r >= 70:
            out["rsi_signal"] = "overbought"
        elif r >= 60:
            out["rsi_signal"] = "approaching_overbought"
        elif r <= 30:
            out["rsi_signal"] = "oversold"
        elif r <= 40:
            out["rsi_signal"] = "approaching_oversold"
        else:
            out["rsi_signal"] = "neutral"

    # MACD signal
    if m:
        if m["histogram"] > 0:
            out["macd_signal"] = "bullish"
        elif m["histogram"] < 0:
            out["macd_signal"] = "bearish"
        else:
            out["macd_signal"] = "neutral"

    # Bollinger position
    if bb:
        bw = bb["upper"] - bb["lower"]
        if bw > 0:
            if price > bb["upper"]:
                out["bollinger_position"] = "above_upper"
            elif price > bb["middle"] + bw * 0.25:
                out["bollinger_position"] = "upper_zone"
            elif price < bb["lower"]:
                out["bollinger_position"] = "below_lower"
            elif price < bb["middle"] - bw * 0.25:
                out["bollinger_position"] = "lower_zone"
            else:
                out["bollinger_position"] = "middle"

    # Support and resistance levels
    support, resistance = [], []
    for key in ma_keys:
        val = out.get(key)
        if val is not None:
            entry = {"level": val, "label": key.upper().replace("_", " ")}
            if val < price:
                support.append(entry)
            else:
                resistance.append(entry)
    if out.get("low_20d") is not None and out["low_20d"] < price:
        support.append({"level": out["low_20d"], "label": "20D Low"})
    if out.get("high_20d") is not None and out["high_20d"] > price:
        resistance.append({"level": out["high_20d"], "label": "20D High"})
    if bb:
        if bb["lower"] < price:
            support.append({"level": round(bb["lower"], 2), "label": "BB Lower"})
        if bb["upper"] > price:
            resistance.append({"level": round(bb["upper"], 2), "label": "BB Upper"})
    support.sort(key=lambda x: x["level"], reverse=True)
    resistance.sort(key=lambda x: x["level"])
    if support:
        out["support_levels"] = support
    if resistance:
        out["resistance_levels"] = resistance

    return out


def _rate(ind: dict, price: float) -> str:
    """Vote across MA stack, RSI, MACD, breakouts → five-level rating."""
    votes = 0
    for ma_key in ("ema_9", "sma_20", "sma_50", "sma_200"):
        ma_val = ind.get(ma_key)
        if ma_val is not None:
            votes += 1 if price > ma_val else -1
    m = ind.get("macd")
    if m:
        votes += 1 if m["histogram"] > 0 else -1
    r = ind.get("rsi_14")
    if r is not None:
        if r >= 60:
            votes += 1
        elif r <= 40:
            votes -= 1
    if ind.get("breakout"):
        votes += 2
    if ind.get("breakdown"):
        votes -= 2

    if votes >= 4:
        return "strong_bullish"
    if votes >= 2:
        return "mild_bullish"
    if votes <= -4:
        return "strong_bearish"
    if votes <= -2:
        return "mild_bearish"
    return "neutral"
