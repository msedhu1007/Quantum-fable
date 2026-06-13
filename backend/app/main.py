"""FastAPI entrypoint — wires routers, DB, and the APScheduler scan loop."""
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from . import growthvalue, momentum
from .config import get_settings
from .db import Base, SessionLocal, engine
from .models import GrowthValueItem, WatchlistItem
from .routers import alerts, growthvalue as growthvalue_router, meta, research, scan, watchlist
from .scanner import market_is_open, scan_all, scan_status

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
settings = get_settings()


def seed_watchlist() -> None:
    with SessionLocal() as db:
        existing = set(db.scalars(select(WatchlistItem.symbol)).all())
        for symbol in settings.default_watchlist.split(","):
            symbol = symbol.strip().upper()
            if symbol and symbol not in existing:
                db.add(WatchlistItem(symbol=symbol))
        db.commit()


def seed_growth_value() -> None:
    """Populate the Growth & Value board so it is not empty out of the box.
    Only seeds an empty table — never re-adds tickers the user has removed."""
    with SessionLocal() as db:
        if db.scalar(select(GrowthValueItem.id).limit(1)) is not None:
            return
        for symbol in settings.default_growth_value_list.split(","):
            symbol = symbol.strip().upper()
            if symbol:
                db.add(GrowthValueItem(symbol=symbol))
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_watchlist()
    seed_growth_value()
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        scan_all,
        "interval",
        minutes=settings.scan_interval_minutes,
        id="watchlist-scan",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        momentum.refresh,
        "interval",
        minutes=15,
        id="momentum-scan",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        growthvalue.refresh,
        "interval",
        minutes=60,
        id="growth-value-scan",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    momentum.refresh_async()  # warm the cache at startup
    growthvalue.refresh_async()
    log.info(
        "Scanner every %s min; momentum every 15 min; growth/value every 60 min",
        settings.scan_interval_minutes,
    )
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Options Signal Alert Engine",
    description="Research and alerting tool — not financial advice or trade execution.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://sedhuhome.ai",
        "https://www.sedhuhome.ai",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(watchlist.router)
app.include_router(alerts.router)
app.include_router(research.router)
app.include_router(scan.router)
app.include_router(meta.router)
app.include_router(growthvalue_router.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "market_open": market_is_open(),
        "scan_interval_minutes": settings.scan_interval_minutes,
        "scanner": scan_status,
    }
