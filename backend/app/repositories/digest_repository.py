from datetime import date
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.digest import DailyDigest, DigestArticle, DigestStatus
from app.models.news import NewsArticle
from app.schemas.news import DigestPreview


class DigestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_date(self, digest_date: date) -> DailyDigest | None:
        return cast(
            DailyDigest | None,
            await self.session.scalar(
                select(DailyDigest)
                .where(DailyDigest.date == digest_date)
                .options(selectinload(DailyDigest.articles).selectinload(DigestArticle.article))
            ),
        )

    async def list_recent(self, limit: int = 90) -> list[DailyDigest]:
        result = await self.session.scalars(
            select(DailyDigest)
            .options(selectinload(DailyDigest.articles).selectinload(DigestArticle.article))
            .order_by(DailyDigest.date.desc())
            .limit(limit)
        )
        return list(result)

    async def get_or_create(self, digest_date: date) -> DailyDigest:
        digest = await self.get_by_date(digest_date)
        if digest is not None:
            return digest
        digest = DailyDigest(date=digest_date, status=DigestStatus.PENDING, articles=[])
        self.session.add(digest)
        await self.session.flush()
        return digest

    async def save_preview(
        self,
        digest: DailyDigest,
        preview: DigestPreview,
        articles_by_url: dict[str, NewsArticle],
    ) -> DailyDigest:
        digest.articles.clear()
        for position, item in enumerate(preview.articles, 1):
            digest.articles.append(
                DigestArticle(
                    article=articles_by_url[item.url],
                    position=position,
                    section=item.category.value,
                    summary=item.summary,
                    why_it_matters=item.why_it_matters,
                )
            )
        digest.intro = preview.intro
        digest.error_message = None
        await self.session.flush()
        return digest
