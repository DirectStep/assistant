from datetime import date, time

from sqlalchemy import JSON, BigInteger, Date, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin

DEFAULT_NEWS_TOPICS = [
    "ai",
    "russian_market",
    "geopolitics",
    "russia_ukraine",
    "startups",
]


class UserSettings(TimestampMixin, Base):
    __tablename__ = "user_settings"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    daily_digest_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(8, 30))
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="Europe/Moscow")
    news_topics: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=lambda: list(DEFAULT_NEWS_TOPICS)
    )
    news_max_articles: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    last_daily_digest_sent_on: Mapped[date | None] = mapped_column(Date)
