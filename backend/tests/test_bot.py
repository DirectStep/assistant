from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

from aiogram import Dispatcher
from aiogram.types import Update, User

from app.bot.application import create_dispatcher
from app.bot.handlers import task_list_messages
from app.bot.keyboards import task_actions_keyboard, web_app_keyboard
from app.bot.middlewares import OwnerOnlyMiddleware
from app.core.config import Settings
from app.main import shutdown_polling
from app.models.task import SourceType, Task
from app.services.task_ingestion_service import fallback_task_title


async def test_owner_middleware_allows_owner() -> None:
    middleware = OwnerOnlyMiddleware(1001)
    called = False

    async def handler(event: Update, data: dict[str, Any]) -> str:
        nonlocal called
        called = True
        return "handled"

    result = await middleware(
        handler,  # type: ignore[arg-type]
        Update(update_id=1),
        {"event_from_user": User(id=1001, is_bot=False, first_name="Стёпа")},
    )

    assert result == "handled"
    assert called is True


async def test_owner_middleware_ignores_other_users() -> None:
    middleware = OwnerOnlyMiddleware(1001)

    async def handler(event: Update, data: dict[str, Any]) -> str:
        raise AssertionError("Handler must not be called")

    result = await middleware(
        handler,  # type: ignore[arg-type]
        Update(update_id=1),
        {"event_from_user": User(id=2002, is_bot=False, first_name="Чужой")},
    )

    assert result is None


def test_task_keyboard_contains_scoped_actions() -> None:
    keyboard = task_actions_keyboard(42)
    callback_values = [button.callback_data for button in keyboard.inline_keyboard[0]]

    assert callback_values == ["task:complete:42", "task:delete:42"]
    assert keyboard.inline_keyboard[0][0].text == "Завершить"


def test_web_app_keyboard_requires_https() -> None:
    assert web_app_keyboard("http://localhost:5173") is None
    assert web_app_keyboard("https://assistant.example.com") is not None


def test_fallback_title_preserves_source_semantics() -> None:
    assert fallback_task_title("  Позвонить   Ивану  ") == "Позвонить Ивану"
    assert fallback_task_title("   \n  ") is None
    assert fallback_task_title("x" * 501) == "x" * 497 + "..."


def test_dispatcher_requires_owner() -> None:
    try:
        create_dispatcher(Settings(owner_telegram_id=None, bot_allow_all_users=False))
    except ValueError as error:
        assert str(error) == "OWNER_TELEGRAM_ID is required to start the bot"
    else:
        raise AssertionError("Dispatcher must reject missing owner ID")


def test_dispatcher_is_configured_for_owner() -> None:
    dispatcher = create_dispatcher(Settings(owner_telegram_id=1001))

    assert dispatcher["settings"].owner_telegram_id == 1001


def test_dispatcher_can_explicitly_allow_all_users() -> None:
    dispatcher = create_dispatcher(Settings(owner_telegram_id=None, bot_allow_all_users=True))

    assert dispatcher["settings"].bot_allow_all_users is True


def test_long_task_list_is_split_into_telegram_sized_messages() -> None:
    tasks = [
        Task(title="&" * 500, telegram_user_id=1001, source_type=SourceType.TEXT) for _ in range(20)
    ]

    messages = task_list_messages("Задачи", tasks, "Europe/Moscow")

    assert len(messages) > 1
    assert all(len(message) <= 4000 for message in messages)


async def test_polling_shutdown_uses_dispatcher_stop() -> None:
    import asyncio

    stopped = asyncio.Event()

    async def polling() -> None:
        await stopped.wait()

    polling_task = asyncio.create_task(polling())
    dispatcher = cast(
        Dispatcher,
        SimpleNamespace(stop_polling=AsyncMock(side_effect=stopped.set)),
    )

    await shutdown_polling(dispatcher, polling_task)

    assert dispatcher.stop_polling.await_count == 1  # type: ignore[attr-defined]
    assert polling_task.done()
    assert polling_task.cancelled() is False
