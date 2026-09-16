from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_telegram_user
from app.api.routes.digests import router as digests_router
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.models.digest import DailyDigest, DigestArticle, DigestStatus
from app.models.news import NewsArticle
from app.news.providers import RssNewsProvider
from app.schemas.auth import TelegramUser
from app.schemas.news import NewsArticleInput, NewsCategory


async def test_generate_digest_preview_persists_real_article(
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fetch_calls = 0

    async def fake_fetch(
        self: RssNewsProvider,
        since: datetime,
        topics: set[NewsCategory],
    ) -> list[NewsArticleInput]:
        nonlocal fetch_calls
        fetch_calls += 1
        return [
            NewsArticleInput(
                title="OpenAI выпустила новую AI-модель",
                url="https://example.com/real-source",
                source="Example News",
                category=NewsCategory.AI,
                published_at=datetime.now(UTC),
                raw_description="OpenAI описала выпуск модели в первичном материале.",
            )
        ]

    monkeypatch.setattr(RssNewsProvider, "fetch", fake_fetch)
    app = build_test_app(database_session, tmp_path)
    digest_date = datetime.now(ZoneInfo("Europe/Moscow")).date()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/digests/generate")
        repeated = await client.post("/digests/generate")
        pdf_response = await client.get(f"/digests/{digest_date.isoformat()}/pdf")
        missing_pdf_response = await client.get(
            f"/digests/{(digest_date - timedelta(days=1)).isoformat()}/pdf"
        )
        archive_response = await client.get("/digests")
        detail_response = await client.get(f"/digests/{digest_date.isoformat()}")
        missing_detail_response = await client.get(
            f"/digests/{(digest_date - timedelta(days=1)).isoformat()}"
        )

    assert response.status_code == 200
    assert repeated.status_code == 200
    body = response.json()
    assert body["fetched_count"] == 1
    assert body["articles"][0]["url"] == "https://example.com/real-source"
    assert "raw_description" not in body["articles"][0]
    assert fetch_calls == 1
    assert await database_session.scalar(select(func.count()).select_from(NewsArticle)) == 1
    assert await database_session.scalar(select(func.count()).select_from(DailyDigest)) == 1
    assert await database_session.scalar(select(func.count()).select_from(DigestArticle)) == 1
    digest = await database_session.scalar(select(DailyDigest))
    assert digest is not None
    assert digest.status == DigestStatus.COMPLETED
    assert digest.pdf_path is not None
    pdf_path = Path(digest.pdf_path)
    assert pdf_path.is_file()
    assert pdf_path.read_bytes().startswith(b"%PDF")
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF")
    assert missing_pdf_response.status_code == 404
    assert archive_response.status_code == 200
    assert archive_response.json() == [
        {
            "date": digest_date.isoformat(),
            "status": "completed",
            "article_count": 1,
            "pdf_available": True,
            "created_at": archive_response.json()[0]["created_at"],
        }
    ]
    assert detail_response.status_code == 200
    assert detail_response.json()["articles"][0]["url"] == "https://example.com/real-source"
    assert missing_detail_response.status_code == 404


def build_test_app(database_session: AsyncSession, digest_output_dir: Path) -> FastAPI:
    app = FastAPI()
    app.include_router(digests_router)

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield database_session

    async def override_user() -> TelegramUser:
        return TelegramUser(id=1781530480, first_name="Стёпа")

    def override_settings() -> Settings:
        return Settings(
            _env_file=None,
            database_url="sqlite+aiosqlite://",
            owner_telegram_id=1781530480,
            openai_api_key=None,
            digest_output_dir=digest_output_dir,
        )

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_telegram_user] = override_user
    app.dependency_overrides[get_settings] = override_settings
    return app
