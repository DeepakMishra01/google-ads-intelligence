"""Typed application settings loaded from environment / .env via pydantic-settings.

`get_settings()` is cached so the whole process shares one immutable Settings
instance; it is the single dependency-injection seam for configuration.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Central configuration object. Never read os.environ directly elsewhere."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_env: Environment = "development"
    app_debug: bool = True
    app_log_level: LogLevel = "INFO"
    app_log_json: bool = False
    api_prefix: str = "/api/v1"

    # --- Database ---
    # Prefer an explicit DATABASE_URL; otherwise assemble from parts. Kept as a
    # plain string so SQLAlchemy driver schemes (e.g. postgresql+psycopg) and
    # SQLite URLs (in tests) are accepted without strict DSN validation.
    database_url: str | None = None
    postgres_user: str = "ads"
    postgres_password: str = "ads"
    postgres_db: str = "ads_intelligence"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # --- Google Ads API ---
    google_ads_developer_token: str = ""
    google_ads_client_id: str = ""
    google_ads_client_secret: str = ""
    google_ads_refresh_token: str = ""
    google_ads_login_customer_id: str = ""
    google_ads_api_version: str = ""
    google_ads_yaml_path: str = ""
    google_ads_client_customer_ids: str = ""  # comma-separated, optional

    # --- Sync engine ---
    scheduler_enabled: bool = True
    sync_hourly_enabled: bool = True
    sync_daily_enabled: bool = True
    sync_daily_hour: int = 4
    scorecard_weekly_enabled: bool = True
    scorecard_weekly_day: str = "mon"  # cron day-of-week for the weekly snapshot
    sync_max_retries: int = 3
    sync_retry_backoff_seconds: int = 30
    sync_default_lookback_days: int = 7

    # --- Security / audit ---
    api_key: str = ""
    audit_enabled: bool = True  # write an audit row for mutating requests
    db_connect_timeout: int = 10  # seconds; bounds hangs to an unreachable DB

    # --- AI Ad Copy Generator ---
    # LLM phrasing is optional: when no key is set the generator falls back to the
    # deterministic (data-driven) backend, so the module always works.
    anthropic_api_key: str = ""
    ad_copy_llm_model: str = "claude-sonnet-5"
    # Gemini is supported for testing; auto = use Anthropic if its key is set,
    # else Gemini, else the deterministic engine. Force with "anthropic"/"gemini".
    gemini_api_key: str = ""
    # Use a non-"thinking" model (flash-lite) — thinking models (2.5-flash, 3.x)
    # spend the output budget on reasoning and truncate the JSON. Override freely.
    gemini_model: str = "gemini-flash-lite-latest"
    ad_copy_llm_provider: str = "auto"  # auto | anthropic | gemini
    ad_copy_llm_enabled: bool = True  # master switch for the hybrid LLM backend
    ad_copy_llm_max_tokens: int = 2000
    keyword_planner_enabled: bool = True  # falls back to historical if unavailable
    landing_page_timeout_seconds: int = 12
    landing_page_max_bytes: int = 2_000_000  # cap fetched HTML to bound memory

    # ------------------------------------------------------------------ #
    # Validators / derived values
    # ------------------------------------------------------------------ #
    @field_validator("google_ads_login_customer_id", mode="before")
    @classmethod
    def _strip_customer_id(cls, v: str) -> str:
        """Google Ads customer ids must be digits only (strip dashes/spaces)."""
        if v is None:
            return ""
        return str(v).replace("-", "").replace(" ", "").strip()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        """Effective DB URI: explicit DATABASE_URL wins, else assembled from parts.

        Managed hosts (Render/Heroku/Neon) hand out ``postgres://`` or
        ``postgresql://`` URLs; normalise those to the psycopg3 driver scheme so
        the app connects without any manual editing of the URL.
        """
        if self.database_url:
            url = self.database_url
            if url.startswith("postgres://"):
                return "postgresql+psycopg://" + url[len("postgres://") :]
            if url.startswith("postgresql://"):
                return "postgresql+psycopg://" + url[len("postgresql://") :]
            return url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def client_customer_id_list(self) -> list[str]:
        """Parsed, normalized list of client customer ids to sync (may be empty)."""
        raw = self.google_ads_client_customer_ids or ""
        return [cid.replace("-", "").strip() for cid in raw.split(",") if cid.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide cached Settings instance."""
    return Settings()
