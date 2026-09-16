import asyncio
import calendar
import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from time import struct_time
from typing import Any, cast

import feedparser  # type: ignore[import-untyped]
import httpx

from app.schemas.news import NewsArticleInput, NewsCategory

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RssSource:
    name: str
    url: str
    category: NewsCategory


class NewsProvider(ABC):
    @abstractmethod
    async def fetch(
        self,
        since: datetime,
        topics: set[NewsCategory],
    ) -> list[NewsArticleInput]:
        raise NotImplementedError


class RssNewsProvider(NewsProvider):
    def __init__(
        self,
        sources: list[RssSource],
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.sources = sources
        self.timeout_seconds = timeout_seconds

    async def fetch(
        self,
        since: datetime,
        topics: set[NewsCategory],
    ) -> list[NewsArticleInput]:
        selected_sources = [source for source in self.sources if source.category in topics]
        if not selected_sources:
            return []

        headers = {"User-Agent": "PersonalAssistantBot/0.1 (+RSS digest)"}
        async with httpx.AsyncClient(
            headers=headers,
            timeout=self.timeout_seconds,
            follow_redirects=True,
        ) as client:
            results = await asyncio.gather(
                *(self._fetch_source(client, source, since) for source in selected_sources),
                return_exceptions=True,
            )

        articles: list[NewsArticleInput] = []
        for source, result in zip(selected_sources, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning("News source failed: %s: %s", source.name, result)
                continue
            articles.extend(result)
        return articles

    async def _fetch_source(
        self,
        client: httpx.AsyncClient,
        source: RssSource,
        since: datetime,
    ) -> list[NewsArticleInput]:
        response = await client.get(source.url)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        entries = cast(list[Mapping[str, Any]], feed.get("entries", []))

        articles: list[NewsArticleInput] = []
        for entry in entries:
            published_at = _entry_datetime(entry)
            if published_at is None or published_at < since:
                continue
            title = str(entry.get("title", "")).strip()
            url = str(entry.get("link", "")).strip()
            if not title or not url:
                continue
            description = str(entry.get("summary", "")).strip()[:10_000] or None
            articles.append(
                NewsArticleInput(
                    title=title,
                    url=url,
                    source=source.name,
                    category=source.category,
                    published_at=published_at,
                    raw_description=description,
                )
            )
        logger.info("Fetched %d articles from %s", len(articles), source.name)
        return articles


def _entry_datetime(entry: Mapping[str, Any]) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if isinstance(value, struct_time):
            return datetime.fromtimestamp(calendar.timegm(value), tz=UTC)
        if isinstance(value, tuple) and len(value) >= 6:
            try:
                return datetime(
                    int(value[0]),
                    int(value[1]),
                    int(value[2]),
                    int(value[3]),
                    int(value[4]),
                    int(value[5]),
                    tzinfo=UTC,
                )
            except (TypeError, ValueError):
                continue
    return None
