from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.news import NewsArticle


class DigestStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DailyDigest(TimestampMixin, Base):
    __tablename__ = "daily_digests"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[DigestStatus] = mapped_column(
        Enum(
            DigestStatus,
            name="digest_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=DigestStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    intro: Mapped[str | None] = mapped_column(Text)

    articles: Mapped[list[DigestArticle]] = relationship(
        back_populates="digest", cascade="all, delete-orphan", order_by="DigestArticle.position"
    )


class DigestArticle(Base):
    __tablename__ = "digest_articles"
    __table_args__ = (UniqueConstraint("digest_id", "position", name="uq_digest_position"),)

    digest_id: Mapped[int] = mapped_column(
        ForeignKey("daily_digests.id", ondelete="CASCADE"), primary_key=True
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)

    digest: Mapped[DailyDigest] = relationship(back_populates="articles")
    article: Mapped[NewsArticle] = relationship(back_populates="digest_links")
