import logging
from datetime import datetime
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, MenuButtonWebApp, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.callbacks import TaskActionCallback
from app.bot.keyboards import task_actions_keyboard, web_app_keyboard
from app.core.config import Settings
from app.models.task import SourceType, Task
from app.repositories.digest_repository import DigestRepository
from app.services.digest_generation_service import generate_digest_for_user
from app.services.settings_service import SettingsService
from app.services.task_ingestion_service import TaskIngestionService, TranscriptionUnavailableError
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)


async def configure_chat_menu_button(message: Message, settings: Settings) -> None:
    """Set a per-chat Mini App button; Telegram applies this reliably to private chats."""
    if not settings.webapp_url.startswith("https://"):
        return
    bot = message.bot
    if bot is None:
        return
    try:
        await bot.set_chat_menu_button(
            chat_id=message.chat.id,
            menu_button=MenuButtonWebApp(
                text="Задачи",
                web_app=WebAppInfo(url=settings.webapp_url),
            ),
        )
    except Exception:
        logger.warning("Could not configure Mini App menu button", exc_info=True)


def format_task(task: Task, timezone: str, position: int | None = None) -> str:
    prefix = f"{position}. " if position is not None else ""
    title = f"<b>{escape(task.title)}</b>" if position is None else escape(task.title)
    lines = [f"{prefix}{title}"]
    if task.due_at is not None:
        due_at = task.due_at.astimezone(ZoneInfo(timezone))
        lines.append(f"Дедлайн: {due_at:%d.%m.%Y}")
    return "\n".join(lines)


def task_list_messages(header: str, tasks: list[Task], timezone: str) -> list[str]:
    messages: list[str] = []
    current = f"<b>{header}</b>"
    for position, task in enumerate(tasks, 1):
        paragraph = format_task(task, timezone, position)
        if len(current) + len(paragraph) + 2 > 4000:
            messages.append(current)
            current = f"<b>{header} — продолжение</b>"
        current += "\n\n" + paragraph
    messages.append(current)
    return messages


async def save_task_from_content(
    message: Message,
    text: str,
    source_type: SourceType,
    source_metadata: dict[str, object] | None,
    task_service: TaskService,
    task_ingestion_service: TaskIngestionService,
    settings: Settings,
    delete_text: str = "Удалить",
) -> None:
    if message.from_user is None:
        return
    task_data = await task_ingestion_service.build_task(text, source_type, source_metadata)
    if task_data is None:
        await message.answer("Пустую задачу не добавил.")
        return

    task = await task_service.create_task(message.from_user.id, task_data)
    await message.answer(
        "Добавлено:\n" + format_task(task, settings.timezone),
        reply_markup=task_actions_keyboard(task.id, delete_text),
    )


async def start_command(message: Message, settings: Settings) -> None:
    await configure_chat_menu_button(message, settings)
    await message.answer(
        "Пришли задачу обычным сообщением.",
        reply_markup=web_app_keyboard(settings.webapp_url),
    )


async def help_command(message: Message) -> None:
    await message.answer(
        "/tasks — активные задачи\n"
        "/today — задачи на сегодня\n"
        "/news — сегодняшняя сводка\n"
        "/app — открыть Mini App\n\n"
        "Любое обычное сообщение будет сохранено как задача."
    )


async def app_command(message: Message, settings: Settings) -> None:
    await configure_chat_menu_button(message, settings)
    keyboard = web_app_keyboard(settings.webapp_url)
    if keyboard is None:
        await message.answer("Mini App URL пока не настроен.")
        return
    await message.answer("Задачи", reply_markup=keyboard)


async def tasks_command(
    message: Message,
    task_service: TaskService,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    tasks = await task_service.list_active_tasks(message.from_user.id, limit=20)
    if not tasks:
        await message.answer("Активных задач нет.")
        return

    for text in task_list_messages("Задачи", tasks, settings.timezone):
        await message.answer(text)


async def today_command(
    message: Message,
    task_service: TaskService,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    tasks = await task_service.list_today_tasks(message.from_user.id)
    if not tasks:
        await message.answer("На сегодня задач нет.")
        return

    for text in task_list_messages("Сегодня", tasks, settings.timezone):
        await message.answer(text)


async def news_command(
    message: Message,
    session: AsyncSession,
    settings: Settings,
) -> None:
    if message.from_user is None:
        return
    user_settings = await SettingsService(session, settings).get_or_create(message.from_user.id)
    digest_date = datetime.now(ZoneInfo(user_settings.timezone)).date()
    try:
        await generate_digest_for_user(session, settings, user_settings, digest_date)
        digest = await DigestRepository(session).get_by_date(digest_date)
        if digest is None or digest.pdf_path is None or not Path(digest.pdf_path).is_file():
            raise FileNotFoundError("Generated digest PDF is missing")
        await message.answer_document(
            FSInputFile(digest.pdf_path, filename=Path(digest.pdf_path).name),
            caption=f"Сводка за {digest_date:%d.%m.%Y}",
        )
    except Exception:
        logger.exception("Digest command failed")
        await message.answer("Не удалось сформировать сводку.")


async def complete_task_callback(
    callback: CallbackQuery,
    callback_data: TaskActionCallback,
    task_service: TaskService,
) -> None:
    if callback.from_user is None:
        return
    task = await task_service.complete_task(callback_data.task_id, callback.from_user.id)
    if task is None:
        await callback.answer("Задача не найдена.", show_alert=True)
        return

    await callback.answer("Готово")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"Готово:\n{escape(task.title)}")


async def delete_task_callback(
    callback: CallbackQuery,
    callback_data: TaskActionCallback,
    task_service: TaskService,
) -> None:
    if callback.from_user is None:
        return
    deleted = await task_service.delete_task(callback_data.task_id, callback.from_user.id)
    if not deleted:
        await callback.answer("Задача не найдена.", show_alert=True)
        return

    await callback.answer("Удалено")
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Задача удалена.")


async def create_forwarded_task(
    message: Message,
    task_service: TaskService,
    task_ingestion_service: TaskIngestionService,
    settings: Settings,
) -> None:
    text = message.text or message.caption
    if text is None or message.forward_origin is None:
        return
    metadata = cast(dict[str, object], message.forward_origin.model_dump(mode="json"))
    await save_task_from_content(
        message,
        text,
        SourceType.FORWARD,
        metadata,
        task_service,
        task_ingestion_service,
        settings,
    )


async def create_voice_task(
    message: Message,
    bot: Bot,
    task_service: TaskService,
    task_ingestion_service: TaskIngestionService,
    settings: Settings,
) -> None:
    if message.voice is None:
        return

    try:
        with TemporaryDirectory(prefix="personal-assistant-voice-") as directory:
            audio_path = Path(directory) / "voice.ogg"
            await bot.download(message.voice, destination=audio_path)
            text = await task_ingestion_service.transcribe_voice(audio_path)
    except TranscriptionUnavailableError:
        await message.answer("Распознавание голоса не настроено.")
        return
    except Exception as error:
        logger.warning("Voice transcription failed: %s", error)
        await message.answer("Не удалось распознать голосовое сообщение.")
        return

    metadata: dict[str, object] = {
        "file_unique_id": message.voice.file_unique_id,
        "duration": message.voice.duration,
    }
    if message.forward_origin is not None:
        metadata["forward_origin"] = cast(
            dict[str, object],
            message.forward_origin.model_dump(mode="json"),
        )
    await save_task_from_content(
        message,
        text,
        SourceType.VOICE,
        metadata,
        task_service,
        task_ingestion_service,
        settings,
        delete_text="Отменить",
    )


async def create_text_task(
    message: Message,
    task_service: TaskService,
    task_ingestion_service: TaskIngestionService,
    settings: Settings,
) -> None:
    if message.from_user is None or message.text is None:
        return
    await save_task_from_content(
        message,
        message.text,
        SourceType.TEXT,
        None,
        task_service,
        task_ingestion_service,
        settings,
    )


def create_task_router() -> Router:
    task_router = Router(name="tasks")
    task_router.message.register(start_command, CommandStart())
    task_router.message.register(help_command, Command("help"))
    task_router.message.register(app_command, Command("app"))
    task_router.message.register(tasks_command, Command("tasks"))
    task_router.message.register(today_command, Command("today"))
    task_router.message.register(news_command, Command("news"))
    task_router.callback_query.register(
        complete_task_callback,
        TaskActionCallback.filter(F.action == "complete"),
    )
    task_router.callback_query.register(
        delete_task_callback,
        TaskActionCallback.filter(F.action == "delete"),
    )
    task_router.message.register(create_voice_task, F.voice)
    task_router.message.register(
        create_forwarded_task,
        F.forward_origin & (F.text | F.caption),
    )
    task_router.message.register(
        create_text_task,
        F.text & ~F.text.startswith("/") & ~F.forward_origin,
    )
    return task_router
