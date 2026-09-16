from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes.telegram import router as telegram_router
from app.core.config import Settings, get_settings


async def test_webhook_rejects_wrong_secret() -> None:
    app, dispatcher = build_webhook_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
            json={"update_id": 1},
        )

    assert response.status_code == 403
    assert dispatcher.feed_update.await_count == 0


async def test_webhook_feeds_valid_update_to_dispatcher() -> None:
    app, dispatcher = build_webhook_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/telegram/webhook",
            headers={"X-Telegram-Bot-Api-Secret-Token": "safe_secret"},
            json={"update_id": 42},
        )

    assert response.status_code == 204
    assert dispatcher.feed_update.await_count == 1
    assert dispatcher.feed_update.await_args.args[1].update_id == 42


def build_webhook_app() -> tuple[FastAPI, SimpleNamespace]:
    app = FastAPI()
    app.include_router(telegram_router)
    dispatcher = SimpleNamespace(feed_update=AsyncMock())
    app.state.telegram_bot = SimpleNamespace()
    app.state.telegram_dispatcher = dispatcher
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite://",
        bot_mode="webhook",
        telegram_webhook_secret="safe_secret",
    )
    return app, dispatcher
