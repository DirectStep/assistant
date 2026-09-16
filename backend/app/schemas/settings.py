from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.settings import DEFAULT_NEWS_TOPICS

ALLOWED_NEWS_TOPICS = frozenset(DEFAULT_NEWS_TOPICS)


class UserSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_digest_time: time | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    news_topics: list[str] | None = None
    news_max_articles: int | None = Field(default=None, ge=5, le=20)

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "UserSettingsUpdate":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self

    @field_validator("daily_digest_time")
    @classmethod
    def require_naive_time(cls, value: time | None) -> time | None:
        if value is not None and value.tzinfo is not None:
            raise ValueError("daily_digest_time must not include timezone")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("Unknown timezone") from error
        return value

    @field_validator("news_topics")
    @classmethod
    def validate_news_topics(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        unique = list(dict.fromkeys(value))
        invalid = set(unique) - ALLOWED_NEWS_TOPICS
        if invalid:
            raise ValueError(f"Unknown news topics: {', '.join(sorted(invalid))}")
        return unique


class UserSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    telegram_user_id: int
    daily_digest_time: time
    timezone: str
    news_topics: list[str]
    news_max_articles: int
