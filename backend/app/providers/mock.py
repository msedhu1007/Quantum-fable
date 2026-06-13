"""Deterministic synthetic market data — run the full pipeline with zero API keys.

Enable with USE_MOCK_DATA=true. Same interface and dict shapes as TradierClient.
Price paths are seeded per symbol so results are stable across calls. Special
symbols for testing the alert path end-to-end:

  BULL — strong uptrend + heavy call flow → should fire a CALL alert
  BEAR — strong downtrend + heavy put flow → should fire a PUT alert
"""
import hashlib
import math
import random
from datetime import date, timedelta


def _rng(symbol: str) -> random.Random:
    seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
    return random.Random(seed)


def _drift(symbol: str) -> float:
    if symbol == "BULL":
        return 0.004
    if symbol == "BEAR":
        return -0.006
    return (_rng(symbol).random() - 0.5) * 0.002


class MockClient:
    configured = True

    def _bars(self, symbol: str, days: int = 320) -> list[dict]:
        rng = _rng(symbol)
        drift = _drift(symbol)
        sigma = 0.006 if symbol in ("BULL", "BEAR") else 0.015  # specials trend cleanly
        price = 50 + rng.random() * 400
        bars = []
        day = date.today() - timedelta(days=days)
        while day <= date.today():
            if day.weekday() < 5:
                change = drift + rng.gauss(0, sigma)
                open_ = price
                close = max(1.0, price * (1 + change))
                high = max(open_, close) * (1 + abs(rng.gauss(0, 0.004)))
                low = min(open_, close) * (1 - abs(rng.gauss(0, 0.004)))
                bars.append({
                    "date": day.isoformat(),
                    "open": round(open_, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": int(2_000_000 * (1 + rng.random() * 3)),
                })
                price = close
        # BULL/BEAR get a volume surge on the final bar so volume confirmation kicks in
            day += timedelta(days=1)
        if symbol in ("BULL", "BEAR") and bars:
            bars[-1]["volume"] = int(bars[-1]["volume"] * 4)
        return bars

    def get_quote(self, symbol: str) -> dict | None:
        bars = self._bars(symbol)
        last, prev = bars[-1], bars[-2]
        return {
            "last": last["close"],
            "volume": last["volume"],
            "change_percentage": round((last["close"] - prev["close"]) / prev["close"] * 100, 2),
        }

    def get_daily_history(self, symbol: str, start: str, end: str) -> list[dict]:
        return [b for b in self._bars(symbol) if start <= b["date"] <= end]

    def get_expirations(self, symbol: str) -> list[str]:
        out, day = [], date.today()
        while len(out) < 6:
            day += timedelta(days=1)
            if day.weekday() == 4:  # Fridays
                out.append(day.isoformat())
        return out

    def get_chain(self, symbol: str, expiration: str) -> list[dict]:
        rng = _rng(f"{symbol}:{expiration}")
        spot = self._bars(symbol)[-1]["close"]
        flow_tilt = {"BULL": 3.0, "BEAR": 1 / 3.0}.get(symbol, 1.0)  # call vol multiplier
        chain = []
        for i in range(-5, 6):
            strike = round(spot * (1 + i * 0.025), 1)
            for option_type in ("call", "put"):
                moneyness = (spot - strike) / spot if option_type == "call" else (strike - spot) / spot
                delta = max(0.02, min(0.98, 0.5 + moneyness * 6))
                if option_type == "put":
                    delta = -delta
                mid = max(0.05, spot * 0.03 * math.exp(-abs(i) * 0.45))
                spread = mid * (0.02 + abs(i) * 0.01)
                liquidity = math.exp(-abs(i) * 0.6)
                volume = int(800 * liquidity * (flow_tilt if option_type == "call" else 1 / flow_tilt)
                             * (0.5 + rng.random()))
                chain.append({
                    "symbol": f"{symbol}{expiration.replace('-', '')}{option_type[0].upper()}{strike}",
                    "description": f"{symbol} {expiration} {strike} {option_type}",
                    "option_type": option_type,
                    "expiration_date": expiration,
                    "strike": strike,
                    "bid": round(mid - spread / 2, 2),
                    "ask": round(mid + spread / 2, 2),
                    "volume": volume,
                    "open_interest": int(3000 * liquidity),
                    "greeks": {"delta": round(delta, 3), "mid_iv": round(0.35 + abs(i) * 0.02, 4)},
                })
        return chain


mock = MockClient()
