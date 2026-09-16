from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsArticle
from app.schemas.news import NewsArticleInput


class NewsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_articles(
        self,
        articles: list[NewsArticleInput],
        relevance_scores: dict[str, int],
    ) -> list[NewsArticle]:
        if not articles:
            return []
        existing = await self.session.scalars(
            select(NewsArticle).where(NewsArticle.url.in_([item.url for item in articles]))
        )
        by_url = {article.url: article for article in existing}
        saved: list[NewsArticle] = []
        for item in articles:
            article = by_url.get(item.url)
            if article is None:
                article = NewsArticle(url=item.url)
                self.session.add(article)
            article.title = item.title
            article.source = item.source
            article.category = item.category.value
            article.published_at = item.published_at
            article.raw_description = item.raw_description
            score = relevance_scores.get(item.url)
            article.relevance_score = float(score) if score is not None else None
            saved.append(article)
        await self.session.flush()
        return saved
