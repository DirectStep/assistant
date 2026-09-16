from datetime import UTC, datetime, timedelta

from app.news.deduplication import canonicalize_url, deduplicate_articles
from app.news.pipeline import NewsPipeline
from app.news.providers import NewsProvider
from app.schemas.news import NewsArticleInput, NewsCategory


class StaticProvider(NewsProvider):
    def __init__(self, articles: list[NewsArticleInput]) -> None:
        self.articles = articles

    async def fetch(
        self,
        since: datetime,
        topics: set[NewsCategory],
    ) -> list[NewsArticleInput]:
        return [
            article
            for article in self.articles
            if article.published_at >= since and article.category in topics
        ]


def make_article(
    title: str,
    url: str,
    *,
    category: NewsCategory = NewsCategory.AI,
    published_at: datetime | None = None,
) -> NewsArticleInput:
    return NewsArticleInput(
        title=title,
        url=url,
        source="Test Source",
        category=category,
        published_at=published_at or datetime.now(UTC),
        raw_description="OpenAI представила новую AI-модель для разработчиков.",
    )


def test_canonicalize_url_removes_tracking_parameters() -> None:
    assert canonicalize_url("https://www.example.com/news/?utm_source=x&id=7#top") == (
        "https://example.com/news?id=7"
    )


def test_news_deduplication_handles_url_title_and_similar_event() -> None:
    now = datetime.now(UTC)
    articles = [
        make_article(
            "OpenAI представила новую модель для разработчиков",
            "https://example.com/a?utm_source=test",
            published_at=now,
        ),
        make_article(
            "OpenAI представила новую модель для разработчиков",
            "https://example.com/a",
            published_at=now - timedelta(minutes=1),
        ),
        make_article(
            "OpenAI представила новую модель для всех разработчиков",
            "https://other.example.com/story",
            published_at=now - timedelta(minutes=2),
        ),
    ]

    unique = deduplicate_articles(articles)

    assert len(unique) == 1
    assert unique[0].url == "https://example.com/a"


async def test_pipeline_builds_json_preview_without_llm() -> None:
    now = datetime(2026, 9, 14, 12, tzinfo=UTC)
    provider = StaticProvider(
        [
            make_article(
                "OpenAI выпустила новую AI-модель",
                "https://example.com/openai-model",
                published_at=now - timedelta(hours=2),
            ),
            make_article(
                "Стартап привлек новый венчурный раунд",
                "https://example.com/startup-round",
                category=NewsCategory.STARTUPS,
                published_at=now - timedelta(hours=3),
            ),
        ]
    )

    preview = await NewsPipeline([provider], None).build_preview(
        {NewsCategory.AI, NewsCategory.STARTUPS, NewsCategory.GEOPOLITICS},
        max_articles=10,
        now=now,
    )

    assert preview.fetched_count == 2
    assert preview.deduplicated_count == 2
    assert len(preview.articles) == 2
    assert preview.articles[0].relevance_score >= preview.articles[1].relevance_score
    assert NewsCategory.GEOPOLITICS in preview.empty_categories
    assert "OpenAI" in preview.intro


async def test_pipeline_without_llm_excludes_untranslated_headlines() -> None:
    now = datetime(2026, 9, 14, 12, tzinfo=UTC)
    russian = make_article(
        "OpenAI представила новую модель",
        "https://example.com/ru",
        published_at=now - timedelta(hours=1),
    )
    english = make_article(
        "AI startup raises a new funding round",
        "https://example.com/en",
        published_at=now - timedelta(hours=1),
    )

    preview = await NewsPipeline([StaticProvider([russian, english])], None).build_preview(
        {NewsCategory.AI},
        max_articles=10,
        now=now,
    )

    assert [article.title for article in preview.articles] == [russian.title]
