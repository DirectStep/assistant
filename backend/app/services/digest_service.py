import asyncio
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.digest import DailyDigest, DigestStatus
from app.news.pipeline import NewsPipeline
from app.pdf.service import DigestPdfService
from app.repositories.digest_repository import DigestRepository
from app.repositories.news_repository import NewsRepository
from app.schemas.news import DigestArticlePreview, DigestPreview, NewsCategory

_generation_lock = asyncio.Lock()


class DigestService:
    def __init__(
        self,
        session: AsyncSession,
        pipeline: NewsPipeline,
        pdf_service: DigestPdfService,
    ) -> None:
        self.session = session
        self.pipeline = pipeline
        self.pdf_service = pdf_service
        self.digest_repository = DigestRepository(session)
        self.news_repository = NewsRepository(session)

    async def generate(
        self,
        digest_date: date,
        topics: set[NewsCategory],
        max_articles: int,
    ) -> DigestPreview:
        async with _generation_lock:
            digest = await self.digest_repository.get_or_create(digest_date)
            if digest.status == DigestStatus.COMPLETED:
                preview = _stored_preview(digest, topics)
                if digest.pdf_path and Path(digest.pdf_path).is_file():
                    return preview
                digest.pdf_path = str(await asyncio.to_thread(self.pdf_service.generate, digest))
                await self.session.commit()
                return preview

            digest.status = DigestStatus.PROCESSING
            digest.error_message = None
            await self.session.commit()
            try:
                preview = await self.pipeline.build_preview(topics, max_articles)
                stored_articles = await self.news_repository.upsert_articles(
                    preview.source_articles,
                    {article.url: article.relevance_score for article in preview.articles},
                )
                await self.digest_repository.save_preview(
                    digest,
                    preview,
                    {article.url: article for article in stored_articles},
                )
                digest.pdf_path = str(await asyncio.to_thread(self.pdf_service.generate, digest))
                digest.status = DigestStatus.COMPLETED
                await self.session.commit()
                return preview
            except Exception as error:
                await self.session.rollback()
                digest = await self.digest_repository.get_or_create(digest_date)
                digest.status = DigestStatus.FAILED
                digest.error_message = str(error)[:2000]
                await self.session.commit()
                raise


def _stored_preview(
    digest: DailyDigest,
    topics: set[NewsCategory],
) -> DigestPreview:
    articles = [
        DigestArticlePreview(
            title=link.article.title,
            url=link.article.url,
            source=link.article.source,
            category=NewsCategory(link.section),
            published_at=link.article.published_at,
            relevance_score=int(link.article.relevance_score or 0),
            summary=link.summary,
            why_it_matters=link.why_it_matters,
            raw_description=link.article.raw_description,
        )
        for link in digest.articles
    ]
    present_categories = {article.category for article in articles}
    generated_at = digest.updated_at or digest.created_at or datetime.now(UTC)
    return DigestPreview(
        generated_at=generated_at,
        intro=digest.intro or "",
        articles=articles,
        empty_categories=sorted(topics - present_categories, key=lambda item: item.value),
        fetched_count=len(articles),
        deduplicated_count=len(articles),
    )
