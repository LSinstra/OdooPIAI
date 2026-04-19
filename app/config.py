from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # Anthropic (also settable from the UI → app_settings table overrides env)
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-opus-4-7"
    CLAUDE_FAST_MODEL: str = "claude-haiku-4-5-20251001"

    # Secrets
    APP_SECRET_KEY: str
    JWT_SECRET: str

    # Bind
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8080
    APP_ENV: str = "production"
    LOG_LEVEL: str = "INFO"
    TIMEZONE: str = "UTC"

    # Database
    POSTGRES_USER: str = "odoopiai"
    POSTGRES_PASSWORD: str = "odoopiai"
    POSTGRES_DB: str = "odoopiai"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    # Behavior
    REDACT_PII: bool = True

    # Scheduler
    DAILY_DIGEST_HOUR: int = 8
    DAILY_DIGEST_MINUTE: int = 0
    RISK_SCAN_INTERVAL_HOURS: int = 4

    # Auto-updater (consumed by scripts/auto-update.sh — declared here so
    # `odoopiai env` can print it).
    UPDATE_BRANCH: str = "claude/odoo-ai-raspberry-pi-8I4Aa"
    UPDATE_INTERVAL_SECONDS: int = 30

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
