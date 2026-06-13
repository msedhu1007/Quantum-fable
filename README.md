# Quantum-Fable — Options Signal Alert Engine

A research and alerting web app that scans a watchlist of tickers during market hours, scores
each setup from news sentiment, price/volume momentum, options flow, IV, and market regime, then
sends **potential CALL / PUT setup** alerts with a concrete liquid contract candidate.

> ⚠️ Research tool only. Not financial advice, no trade execution, no profit guarantees.
> Options involve substantial risk.

## Architecture

```
Next.js frontend (3000)
        │
FastAPI backend (8000) ── APScheduler scan loop (every N min, market hours)
        │                        │
   PostgreSQL/SQLite      Tradier or Polygon (quotes, history, chains + Greeks)
                          Finnhub + Benzinga (news, sentiment, earnings)
                          Anthropic Claude (optional reasoning layer)
                                 │
                          Telegram / Discord / Slack / Email (SMTP or SendGrid)
                          Twilio SMS / ntfy push alerts
```

Hard deterministic rules (liquidity, Delta 0.30–0.60, 7–45 DTE, OI > 500, volume > 100,
spread < 15%, score thresholds ±70) decide whether a setup qualifies. The LLM layer only
explains, classifies confidence, and can downgrade to NO TRADE — it can never flip direction
or bypass the filters.

## Quick start (local)

```sh
cp .env.example .env        # add TRADIER_API_KEY (or POLYGON_API_KEY) + FINNHUB_API_KEY at minimum

# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

SQLite (`backend/dev.db`) is used unless `DATABASE_URL` points at PostgreSQL.

## Quick start (Docker)

```sh
cp .env.example .env
docker compose up --build   # frontend :3000, backend :8000, postgres :5432
```

## API

| Endpoint | Description |
|---|---|
| `GET /health` | Status + market-open flag |
| `GET/POST /watchlist`, `DELETE /watchlist/{sym}` | Manage scanned tickers |
| `POST /scan` / `POST /scan/{sym}` | Manual scan (all or one) |
| `GET /alerts?actionable_only=true` | Alert history |
| `GET /research/{sym}` | Live research snapshot (score, candidates, news) |
| `GET /providers` | Provider + alert-channel configuration status |
| `GET /settings` | Effective scanner thresholds and contract filters |

## Configuration

All knobs are env vars — see [.env.example](.env.example). Alert channels activate
automatically when their credentials are present.

**Mock mode:** `USE_MOCK_DATA=true` runs the entire pipeline — indicators, scoring,
contract selection, alert formatting — on deterministic synthetic data with zero API
keys. Test tickers `BULL` and `BEAR` produce strong trending setups (`BULL` fires a
CALL alert end-to-end).

**Market data:** Tradier is used when `TRADIER_API_KEY` is set, otherwise Polygon.
When Finnhub is configured its real-time quote overrides the (possibly delayed)
Polygon price. Technicals (EMA9, SMA20/50/200, RSI, MACD, Bollinger, ATR, breakouts,
gaps) and Finnhub fundamentals feed five-level ratings into the scoring engine.
Repeated alerts for the same symbol + direction are suppressed for
`ALERT_COOLDOWN_MINUTES` (default 60).
A free Tradier account token gives full options chains with Greeks; on Polygon the
options chain snapshot requires an Options plan — without it the scanner still runs
(price, trend, news) but cannot surface contract candidates, so CALL/PUT alerts
never fire. Finnhub's `/news-sentiment` endpoint is premium-only; when unavailable
the sentiment component of the score is simply skipped.

## Roadmap

- **Phase 3:** IV rank from history, unusual-volume detection, earnings-risk filter, backtesting, confidence tracking.
- **Phase 4:** User accounts, custom alert rules, rate limiting, paper-trading mode.
