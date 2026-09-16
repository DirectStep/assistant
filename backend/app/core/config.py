import re
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Native development reads backend/.env; containers receive settings
        # through environment variables from Compose.
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Personal Assistant"
    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"

    database_url: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "assistant"
    postgres_user: str = "assistant"
    postgres_password: str = "assistant"

    telegram_bot_token: str | None = None
    owner_telegram_id: int | None = Field(default=None, gt=0)
    openai_api_key: str | None = None
    openai_task_model: str = "gpt-5-mini"
    openai_transcription_model: str = "gpt-4o-mini-transcribe"
    openai_news_model: str = "gpt-5-mini"
    app_base_url: str = "http://localhost:8080"
    webapp_url: str = "http://localhost:5173"
    bot_mode: Literal["polling", "webhook"] = "polling"
    bot_allow_all_users: bool = False
    telegram_webhook_secret: str | None = None

    timezone: str = "Europe/Moscow"
    daily_digest_time: str = "08:30"
    news_max_articles: int = Field(default=10, ge=5, le=20)
    digest_output_dir: Path = Path("digests")

    dev_auth: bool = False
    dev_telegram_user_id: int | None = Field(default=None, gt=0)
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @field_validator(
        "telegram_bot_token",
        "openai_api_key",
        "telegram_webhook_secret",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("owner_telegram_id", "dev_telegram_user_id", mode="before")
    @classmethod
    def empty_integer_to_none(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("postgres_db")
    @classmethod
    def validate_postgres_database_name(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError(
                "POSTGRES_DB may only contain letters, digits, dots, dashes and underscores"
            )
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("TIMEZONE must be a valid IANA timezone") from error
        return value

    @field_validator("daily_digest_time")
    @classmethod
    def validate_daily_digest_time(cls, value: str) -> str:
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("DAILY_DIGEST_TIME must use HH:MM format")
        return value

    @field_validator("telegram_webhook_secret")
    @classmethod
    def validate_webhook_secret(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", value):
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET may only contain letters, digits, dashes and underscores"
            )
        return value

    @model_validator(mode="after")
    def build_database_url(self) -> "Settings":
        if self.database_url:
            return self

        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        self.database_url = (
            f"postgresql+asyncpg://{user}:{password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        return self

    @model_validator(mode="after")
    def protect_production_auth(self) -> "Settings":
        if self.app_env == "production" and not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required in production")
        if self.app_env == "production" and not self.owner_telegram_id:
            raise ValueError("OWNER_TELEGRAM_ID is required in production")
        if self.app_env == "production" and self.dev_auth:
            raise ValueError("DEV_AUTH cannot be enabled in production")
        if self.app_env == "production" and self.bot_allow_all_users:
            raise ValueError("BOT_ALLOW_ALL_USERS cannot be enabled in production")
        if self.app_env == "production" and not self.webapp_url.startswith("https://"):
            raise ValueError("WEBAPP_URL must use HTTPS in production")
        if self.app_env == "production" and self.bot_mode == "webhook":
            if not self.app_base_url.startswith("https://"):
                raise ValueError("APP_BASE_URL must use HTTPS for webhook mode")
            if not self.telegram_webhook_secret:
                raise ValueError("TELEGRAM_WEBHOOK_SECRET is required for webhook mode")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
