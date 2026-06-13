"""Application configuration loaded from environment / .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database — SQLite for local dev, point at PostgreSQL in production.
    database_url: str = "sqlite:///./dev.db"

    # Market data providers (Tradier preferred when configured, Polygon fallback)
    tradier_api_key: str = ""
    tradier_base_url: str = "https://sandbox.tradier.com/v1"  # https://api.tradier.com/v1 for prod
    polygon_api_key: str = ""
    polygon_base_url: str = "https://api.polygon.io"
    finnhub_api_key: str = ""
    finnhub_base_url: str = "https://finnhub.io/api/v1"
    alpha_vantage_api_key: str = ""
    alpha_vantage_base_url: str = "https://www.alphavantage.co"
    benzinga_api_key: str = ""
    benzinga_base_url: str = "https://api.benzinga.com/api/v2"
    quiver_api_key: str = ""  # congressional trading via Quiver Quant

    # LLM reasoning layer (optional — deterministic scoring works without it)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # Alert channels (all optional; configured channels are used)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    slack_webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email_from: str = ""
    alert_email_to: str = ""
    sendgrid_api_key: str = ""
    alert_email: str = ""  # SendGrid to-address (and from-address unless alert_email_from set)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from: str = ""
    alert_phone: str = ""
    ntfy_topic: str = ""
    ntfy_base_url: str = "https://ntfy.sh"

    # Scanner behaviour
    use_mock_data: bool = False  # synthetic provider — run the full pipeline with no API keys
    alert_cooldown_minutes: int = 60  # don't re-dispatch same symbol+direction within this window
    scan_interval_minutes: int = 5
    market_hours_only: bool = True
    call_score_threshold: int = 70
    put_score_threshold: int = -70
    default_watchlist: str = (
        "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,AMD,AVGO,NFLX,"
        "CRM,ORCL,ADBE,INTC,MU,QCOM,PLTR,COIN,SHOP,UBER,"
        "ABNB,DIS,BA,CAT,JPM,GS,BAC,XOM,CVX,WMT,"
        "COST,HD,LLY,UNH,JNJ,PFE,SPY,QQQ,IWM,SMH"
    )
    max_watchlist: int = 50
    market_benchmark: str = "SPY"

    # Contract filters
    min_dte: int = 7
    max_dte: int = 45
    min_open_interest: int = 500
    min_volume: int = 100
    max_spread_pct: float = 15.0
    min_abs_delta: float = 0.30
    max_abs_delta: float = 0.60


@lru_cache
def get_settings() -> Settings:
    return Settings()
