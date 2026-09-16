from collections.abc import AsyncIterator

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_telegram_user
from app.api.routes.settings import router as settings_router
from app.api.routes.tasks import router as tasks_router
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.schemas.auth import TelegramUser


async def test_task_crud_api(database_session: AsyncSession) -> None:
    app = build_test_app(database_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/tasks",
            json={
                "title": "  Подготовить презентацию  ",
                "importance": "important",
                "status": "inbox",
            },
        )
        assert created.status_code == 201
        task = created.json()
        assert task["title"] == "Подготовить презентацию"
        assert task["source_type"] == "webapp"

        task_id = task["id"]
        moved = await client.post(f"/tasks/{task_id}/move", json={"status": "today"})
        assert moved.status_code == 200
        assert moved.json()["status"] == "today"

        updated = await client.patch(
            f"/tasks/{task_id}",
            json={"description": "Для встречи с Альфой"},
        )
        assert updated.status_code == 200
        assert updated.json()["description"] == "Для встречи с Альфой"

        completed = await client.post(f"/tasks/{task_id}/complete")
        assert completed.status_code == 200
        assert completed.json()["status"] == "done"
        assert completed.json()["completed_at"] is not None

        listed = await client.get("/tasks")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [task_id]

        deleted = await client.delete(f"/tasks/{task_id}")
        assert deleted.status_code == 204
        assert (await client.get(f"/tasks/{task_id}")).status_code == 404


async def test_settings_api(database_session: AsyncSession) -> None:
    app = build_test_app(database_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        initial = await client.get("/settings")
        assert initial.status_code == 200
        assert initial.json()["news_max_articles"] == 10

        changed = await client.patch(
            "/settings",
            json={
                "daily_digest_time": "09:15:00",
                "news_topics": ["ai", "startups"],
                "news_max_articles": 12,
            },
        )
        assert changed.status_code == 200
        assert changed.json()["daily_digest_time"] == "09:15:00"
        assert changed.json()["news_topics"] == ["ai", "startups"]
        assert changed.json()["news_max_articles"] == 12


async def test_create_done_task_sets_completion_time(database_session: AsyncSession) -> None:
    app = build_test_app(database_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/tasks",
            json={
                "title": "Уже сделано",
                "importance": "normal",
                "status": "done",
            },
        )

    assert created.status_code == 201
    assert created.json()["completed_at"] is not None


async def test_settings_reject_null_and_unknown_fields(database_session: AsyncSession) -> None:
    app = build_test_app(database_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.patch("/settings", json={"timezone": None})).status_code == 422
        assert (await client.patch("/settings", json={"unknown": True})).status_code == 422


def build_test_app(database_session: AsyncSession) -> FastAPI:
    app = FastAPI()
    app.include_router(tasks_router)
    app.include_router(settings_router)

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield database_session

    async def override_user() -> TelegramUser:
        return TelegramUser(id=1781530480, first_name="Стёпа")

    def override_settings() -> Settings:
        return Settings(
            _env_file=None,
            database_url="sqlite+aiosqlite://",
            owner_telegram_id=1781530480,
            daily_digest_time="08:30",
            timezone="Europe/Moscow",
        )

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_telegram_user] = override_user
    app.dependency_overrides[get_settings] = override_settings
    return app
