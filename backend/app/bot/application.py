from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, MenuButtonCommands, MenuButtonWebApp, WebAppInfo

from app.bot.handlers import create_task_router
from app.bot.middlewares import DatabaseSessionMiddleware, OwnerOnlyMiddleware
from app.core.config import Settings
from app.core.database import async_session_factory
from app.services.llm_service import LLMService
from app.services.task_ingestion_service import TaskIngestionService


async def configure_bot_commands(
    bot: Bot,
    webapp_url: str,
    owner_telegram_id: int | None = None,
) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать работу"),
            BotCommand(command="tasks", description="Активные задачи"),
            BotCommand(command="today", description="Задачи на сегодня"),
            BotCommand(command="news", description="Сегодняшняя сводка"),
            BotCommand(command="app", description="Открыть Mini App"),
            BotCommand(command="help", description="Помощь"),
        ]
    )
    if webapp_url.startswith("https://"):
        menu_button = MenuButtonWebApp(
            text="Задачи",
            web_app=WebAppInfo(url=webapp_url),
        )
        await bot.set_chat_menu_button(menu_button=menu_button)
        if owner_telegram_id is not None:
            await bot.set_chat_menu_button(
                chat_id=owner_telegram_id,
                menu_button=menu_button,
            )
    else:
        # Never leave a stale temporary/public Mini App URL configured in Telegram.
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())


def create_dispatcher(settings: Settings) -> Dispatcher:
    if settings.owner_telegram_id is None and not settings.bot_allow_all_users:
        raise ValueError("OWNER_TELEGRAM_ID is required to start the bot")

    dispatcher = Dispatcher()
    dispatcher["settings"] = settings
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
    dispatcher["llm_service"] = llm_service
    dispatcher["task_ingestion_service"] = TaskIngestionService(llm_service, settings.timezone)

    database_middleware = DatabaseSessionMiddleware(async_session_factory, settings.timezone)

    if not settings.bot_allow_all_users:
        if settings.owner_telegram_id is None:
            raise ValueError("OWNER_TELEGRAM_ID is required to start the bot")
        owner_middleware = OwnerOnlyMiddleware(settings.owner_telegram_id)
        dispatcher.message.outer_middleware(owner_middleware)
        dispatcher.callback_query.outer_middleware(owner_middleware)
    dispatcher.message.middleware(database_middleware)
    dispatcher.callback_query.middleware(database_middleware)
    dispatcher.include_router(create_task_router())
    return dispatcher
