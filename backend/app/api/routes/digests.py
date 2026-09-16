from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_telegram_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.models.digest import DailyDigest
from app.repositories.digest_repository import DigestRepository
from app.schemas.auth import TelegramUser
from app.schemas.news import (
    DigestArchiveItem,
    DigestArticlePreview,
    DigestDetail,
    DigestPreview,
    NewsCategory,
)
from app.services.digest_generation_service import generate_digest_for_user
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/digests", tags=["digests"])
CurrentUser = Annotated[TelegramUser, Depends(get_current_telegram_user)]
Session = Annotated[AsyncSession, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=list[DigestArchiveItem])
async def list_digests(
    _user: CurrentUser,
    session: Session,
) -> list[DigestArchiveItem]:
    digests = await DigestRepository(session).list_recent()
    return [
        DigestArchiveItem(
            date=digest.date,
            status=digest.status,
            article_count=len(digest.articles),
            pdf_available=bool(digest.pdf_path and Path(digest.pdf_path).is_file()),
            created_at=digest.created_at,
        )
        for digest in digests
    ]


@router.post("/generate", response_model=DigestPreview)
async def generate_digest_preview(
    user: CurrentUser,
    session: Session,
    settings: AppSettings,
) -> DigestPreview:
    user_settings = await SettingsService(session, settings).get_or_create(user.id)
    return await generate_digest_for_user(
        session,
        settings,
        user_settings,
        datetime.now(ZoneInfo(user_settings.timezone)).date(),
    )


@router.get("/{digest_date}/pdf", response_class=FileResponse)
async def download_digest_pdf(
    digest_date: date,
    _user: CurrentUser,
    session: Session,
) -> FileResponse:
    digest = await DigestRepository(session).get_by_date(digest_date)
    pdf_path = Path(digest.pdf_path) if digest and digest.pdf_path else None
    if pdf_path is None or not pdf_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Digest PDF not found",
        )
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"daily_digest_{digest_date.isoformat()}.pdf",
    )


@router.get("/{digest_date}", response_model=DigestDetail)
async def get_digest(
    digest_date: date,
    _user: CurrentUser,
    session: Session,
) -> DigestDetail:
    digest = await DigestRepository(session).get_by_date(digest_date)
    if digest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Digest not found",
        )
    return _digest_detail(digest)


def _digest_detail(digest: DailyDigest) -> DigestDetail:
    return DigestDetail(
        date=digest.date,
        status=digest.status,
        intro=digest.intro or "",
        pdf_available=bool(digest.pdf_path and Path(digest.pdf_path).is_file()),
        articles=[
            DigestArticlePreview(
                title=link.article.title,
                url=link.article.url,
                source=link.article.source,
                category=NewsCategory(link.section),
                published_at=link.article.published_at,
                relevance_score=int(link.article.relevance_score or 0),
                summary=link.summary,
                why_it_matters=link.why_it_matters,
            )
            for link in digest.articles
        ],
    )
