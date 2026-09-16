from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.settings import UserSettings
from app.news.pipeline import NewsPipeline
from app.news.providers import RssNewsProvider
from app.news.sources import DEFAULT_RSS_SOURCES
from app.pdf.service import DigestPdfService
from app.schemas.news import DigestPreview, NewsCategory
from app.services.digest_service import DigestService
from app.services.llm_service import LLMService


async def generate_digest_for_user(
    session: AsyncSession,
    settings: Settings,
    user_settings: UserSettings,
    digest_date: date,
) -> DigestPreview:
    topics = {
        NewsCategory(topic)
        for topic in user_settings.news_topics
        if topic in NewsCategory._value2member_map_
    }
    llm_service = (
        LLMService(
            settings.openai_api_key,
            settings.openai_task_model,
            settings.openai_transcription_model,
            settings.openai_news_model,
        )
        if settings.openai_api_key
        else None
    )
    try:
        pipeline = NewsPipeline(
            [RssNewsProvider(DEFAULT_RSS_SOURCES)],
            llm_service,
        )
        return await DigestService(
            session,
            pipeline,
            DigestPdfService(settings.digest_output_dir),
        ).generate(
            digest_date,
            topics,
            user_settings.news_max_articles,
        )
    finally:
        if llm_service is not None:
            await llm_service.close()
