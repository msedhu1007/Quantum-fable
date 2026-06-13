# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Options Signal Alert Engine — a research/alerting web app (NOT a trading or advice tool). FastAPI
backend scans watchlist tickers, scores setups (news sentiment, momentum, options flow, IV,
market regime), persists snapshots/alerts, and dispatches CALL/PUT alert messages. Next.js
frontend renders dashboard, watchlist, alert history, and per-ticker research.

## Commands

```sh
# Backend (from backend/, Python 3.11+)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (from frontend/, Node 20+)
npm install
npm run dev          # port 3000
npm run build
npm run typecheck    # tsc --noEmit

# Full stack
docker compose up --build
```

No test suite yet — verify backend changes with `python -c "from app.main import app"` from
`backend/` and frontend changes with `npm run typecheck`.

## Architecture

- `backend/app/config.py` — all tunables are env vars via pydantic-settings (`.env` at repo root
  for Docker, `backend/.env` for bare uvicorn). SQLite default; `DATABASE_URL` for Postgres.
- `backend/app/scanner.py` — orchestration core: `scan_all()` (APScheduler entrypoint, started
  in `main.py` lifespan) → `scan_ticker()` → `gather_ticker_data()` (indicators + options
  metrics via `market_provider()`, Finnhub/Benzinga news + sentiment + earnings) →
  `scoring.score_signal()` → `scoring.make_alert()` → persist + `alerts.dispatch()`.
- `backend/app/scoring.py` — deterministic rules. **Hard rules gate everything**: contract
  filters (Delta 0.30–0.60, 7–45 DTE, OI>500, vol>100, spread<15%) and ±70 score thresholds.
- `backend/app/analyst.py` — optional Claude layer (active only when `ANTHROPIC_API_KEY` set).
  It may add reasons/risks/confidence and downgrade to NO TRADE, but never flips direction or
  bypasses filters — keep that invariant.
- `backend/app/providers/` — one client per data vendor (tradier.py, polygon.py, finnhub.py,
  benzinga.py, mock.py). Each exposes `.configured`; scanner skips work when keys are missing.
  `scanner.market_provider()` picks mock (`USE_MOCK_DATA=true`), else Tradier, else Polygon —
  all expose the same get_quote/get_daily_history/get_expirations/get_chain surface in Tradier
  dict shapes. Finnhub real-time quote overrides provider price when configured.
- `backend/app/technicals.py` — pure-function indicator suite (EMA9, SMA20/50/200, RSI, MACD,
  Bollinger, ATR, breakout/gap) + five-level `technical_rating`; `scoring.rate_fundamentals()`
  rates Finnhub metrics. Both ratings feed `score_signal()` (tech ±30, fund ±20, news ±25,
  flow ±20, market ±10). Mock test tickers BULL/BEAR exercise the alert path keylessly.
- `frontend/lib/api.ts` — single typed API client; all pages are client components fetching
  from `NEXT_PUBLIC_API_URL` (default http://localhost:8000).

## Constraints

- Alert copy must stay hedged: "Potential CALL setup", confidence, risks, invalidation — never
  "buy this", "guaranteed", or directional certainty. A compliance footer is appended in
  `alerts.format_alert()`.
- Tradier sandbox base URL is the default; production data requires `TRADIER_BASE_URL` override.
- Scanner respects `MARKET_HOURS_ONLY` (US/Eastern 9:30–16:00, weekdays) — manual
  `/scan/{ticker}` bypasses the market-hours check, `/scan` (all) does not.
