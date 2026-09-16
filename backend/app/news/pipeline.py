import asyncio
import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from html import unescape
from typing import Protocol

from app.news.deduplication import deduplicate_articles
from app.news.providers import NewsProvider
from app.schemas.news import (
    DigestArticlePreview,
    DigestIntro,
    DigestPreview,
    NewsArticleInput,
    NewsCategory,
    NewsScore,
    NewsSummary,
)

logger = logging.getLogger(__name__)

USER_INTERESTS = [
    "AI и новые AI-продукты",
    "OpenAI, Anthropic, Google и новые модели",
    "AI-агенты, AI-инструменты и AI для бизнеса",
    "российские акции, облигации, ключевая ставка, ЦБ РФ и Московская биржа",
    "геополитика, Россия, Украина, санкции и переговоры",
    "стартапы, венчурный рынок, раунды, IPO и банкротства",
]

KEYWORDS = {
    NewsCategory.AI: ("ai", "ии", "openai", "anthropic", "модель", "agent", "nvidia"),
    NewsCategory.RUSSIAN_MARKET: (
        "акци",
        "облигац",
        "цб",
        "ставк",
        "мосбирж",
        "рубл",
    ),
    NewsCategory.GEOPOLITICS: ("санкц", "переговор", "геополит", "войн", "саммит"),
    NewsCategory.RUSSIA_UKRAINE: ("росси", "украин", "киев", "москв", "перемири"),
    NewsCategory.STARTUPS: ("startup", "стартап", "венчур", "раунд", "ipo", "funding"),
}

WHY_IT_MATTERS = {
    NewsCategory.AI: "Может повлиять на возможности и стоимость AI-инструментов.",
    NewsCategory.RUSSIAN_MARKET: "Может повлиять на российские активы и инвестиционные решения.",
    NewsCategory.GEOPOLITICS: "Может изменить международные риски и экономический фон.",
    NewsCategory.RUSSIA_UKRAINE: "Важно для оценки политических и экономических рисков региона.",
    NewsCategory.STARTUPS: "Показывает изменения на рынке технологий и венчурного капитала.",
}


class NewsLLM(Protocol):
    async def score_news_relevance(
        self,
        articles: list[NewsArticleInput],
        interests: list[str],
    ) -> list[NewsScore]: ...

    async def summarize_news(self, articles: list[NewsArticleInput]) -> list[NewsSummary]: ...

    async def build_digest_intro(self, articles: list[NewsSummary]) -> DigestIntro: ...


class NewsPipeline:
    def __init__(self, providers: Sequence[NewsProvider], llm_service: NewsLLM | None) -> None:
        self.providers = providers
        self.llm_service = llm_service

    async def build_preview(
        self,
        topics: set[NewsCategory],
        max_articles: int,
        *,
        now: datetime | None = None,
    ) -> DigestPreview:
        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        since = current_time - timedelta(hours=24)

        logger.info("News fetch started")
        results = await asyncio.gather(
            *(provider.fetch(since, topics) for provider in self.providers),
            return_exceptions=True,
        )
        fetched: list[NewsArticleInput] = []
        for result in results:
            if isinstance(result, BaseException):
                logger.warning("News provider failed: %s", result)
                continue
            fetched.extend(result)
        logger.info("Articles fetched: %d", len(fetched))

        unique = deduplicate_articles(fetched)
        candidates = _shortlist_candidates(unique, topics, max_articles, current_time)
        if self.llm_service is None:
            candidates = [article for article in candidates if _has_cyrillic(article.title)]
        scored = await self._score(candidates, current_time)
        selected = [item for item in scored if item[1] >= 45][:max_articles]
        selected_articles = [item[0] for item in selected]
        summaries = await self._summarize(selected_articles)
        summary_by_index = {summary.index: summary for summary in summaries}

        previews: list[DigestArticlePreview] = []
        for index, (article, score) in enumerate(selected):
            summary = summary_by_index.get(index) or _fallback_summary(index, article)
            previews.append(
                DigestArticlePreview(
                    title=summary.headline,
                    url=article.url,
                    source=article.source,
                    category=article.category,
                    published_at=article.published_at,
                    relevance_score=score,
                    summary=summary.summary,
                    why_it_matters=summary.why_it_matters,
                    raw_description=article.raw_description,
                )
            )

        intro = await self._build_intro(
            [
                summary_by_index.get(index) or _fallback_summary(index, article)
                for index, article in enumerate(selected_articles)
            ]
        )
        present_categories = {article.category for article in selected_articles}
        logger.info("Articles selected: %d", len(previews))
        return DigestPreview(
            generated_at=current_time,
            intro=intro,
            articles=previews,
            empty_categories=sorted(topics - present_categories, key=lambda item: item.value),
            fetched_count=len(fetched),
            deduplicated_count=len(unique),
            source_articles=unique,
        )

    async def _score(
        self,
        articles: list[NewsArticleInput],
        now: datetime,
    ) -> list[tuple[NewsArticleInput, int]]:
        scores: dict[int, NewsScore] = {}
        if self.llm_service and articles:
            try:
                scores = {
                    score.index: score
                    for score in await self.llm_service.score_news_relevance(
                        articles,
                        USER_INTERESTS,
                    )
                    if score.index < len(articles)
                }
            except Exception:
                logger.warning("LLM news scoring failed; using local ranking", exc_info=True)

        ranked: list[tuple[NewsArticleInput, int]] = []
        for index, article in enumerate(articles):
            llm_score = scores.get(index)
            if llm_score:
                article = article.model_copy(update={"category": llm_score.category})
                score = llm_score.relevance_score
            else:
                score = _fallback_score(article, now)
            ranked.append((article, score))
        return sorted(ranked, key=lambda item: (item[1], item[0].published_at), reverse=True)

    async def _summarize(self, articles: list[NewsArticleInput]) -> list[NewsSummary]:
        if self.llm_service and articles:
            try:
                return [
                    summary
                    for summary in await self.llm_service.summarize_news(articles)
                    if summary.index < len(articles)
                ]
            except Exception:
                logger.warning("LLM news summary failed; using source descriptions", exc_info=True)
        return [_fallback_summary(index, article) for index, article in enumerate(articles)]

    async def _build_intro(self, summaries: list[NewsSummary]) -> str:
        if not summaries:
            return "За последние 24 часа значимых новостей по выбранным темам не найдено."
        if self.llm_service:
            try:
                return (await self.llm_service.build_digest_intro(summaries)).text
            except Exception:
                logger.warning("LLM digest intro failed; using headline list", exc_info=True)
        return "\n".join(f"• {summary.headline}" for summary in summaries[:5])


def _fallback_score(article: NewsArticleInput, now: datetime) -> int:
    haystack = f"{article.title} {article.raw_description or ''}".casefold()
    keyword_matches = sum(keyword in haystack for keyword in KEYWORDS[article.category])
    age_hours = max(0.0, (now - article.published_at).total_seconds() / 3600)
    recency_bonus = 10 if age_hours <= 6 else 5 if age_hours <= 12 else 0
    return min(100, 40 + keyword_matches * 10 + recency_bonus)


def _shortlist_candidates(
    articles: list[NewsArticleInput],
    topics: set[NewsCategory],
    max_articles: int,
    now: datetime,
) -> list[NewsArticleInput]:
    per_category_limit = max(8, max_articles)
    shortlisted: list[NewsArticleInput] = []
    for category in topics:
        category_articles = [article for article in articles if article.category == category]
        category_articles.sort(
            key=lambda article: (_fallback_score(article, now), article.published_at),
            reverse=True,
        )
        shortlisted.extend(category_articles[:per_category_limit])
    return shortlisted


def _fallback_summary(index: int, article: NewsArticleInput) -> NewsSummary:
    raw_text = re.sub(r"<[^>]+>", " ", article.raw_description or "")
    clean_text = " ".join(unescape(raw_text).split())
    summary = clean_text[:500].rstrip(" ,.;") or article.title
    return NewsSummary(
        index=index,
        headline=article.title,
        summary=summary,
        why_it_matters=WHY_IT_MATTERS[article.category],
    )


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text))
