from datetime import date, datetime
from enum import StrEnum
from urllib.parse import urlparse

from pydantic import BaseModel, Field, RootModel, field_validator

from app.models.digest import DigestStatus


class NewsCategory(StrEnum):
    AI = "ai"
    RUSSIAN_MARKET = "russian_market"
    GEOPOLITICS = "geopolitics"
    RUSSIA_UKRAINE = "russia_ukraine"
    STARTUPS = "startups"


class NewsArticleInput(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    url: str = Field(min_length=1, max_length=2048)
    source: str = Field(min_length=1, max_length=200)
    category: NewsCategory
    published_at: datetime
    raw_description: str | None = None

    @field_validator("title", "source")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("News URL must be an absolute HTTP(S) URL")
        return value


class NewsScore(BaseModel):
    index: int = Field(ge=0)
    relevance_score: int = Field(ge=0, le=100)
    category: NewsCategory


class NewsScoreBatch(RootModel[list[NewsScore]]):
    pass


class NewsSummary(BaseModel):
    index: int = Field(ge=0)
    headline: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=800)
    why_it_matters: str = Field(min_length=1, max_length=800)


class NewsSummaryBatch(RootModel[list[NewsSummary]]):
    pass


class DigestIntro(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


class DigestArticlePreview(BaseModel):
    title: str
    url: str
    source: str
    category: NewsCategory
    published_at: datetime
    relevance_score: int
    summary: str
    why_it_matters: str
    raw_description: str | None = Field(default=None, exclude=True)


class DigestPreview(BaseModel):
    generated_at: datetime
    intro: str
    articles: list[DigestArticlePreview]
    empty_categories: list[NewsCategory]
    fetched_count: int
    deduplicated_count: int
    source_articles: list[NewsArticleInput] = Field(default_factory=list, exclude=True)


class DigestArchiveItem(BaseModel):
    date: date
    status: DigestStatus
    article_count: int
    pdf_available: bool
    created_at: datetime


class DigestDetail(BaseModel):
    date: date
    status: DigestStatus
    intro: str
    pdf_available: bool
    articles: list[DigestArticlePreview]
