import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.bot import configure_bot_commands, create_dispatcher
from app.core.config import Settings, get_settings
from app.core.database import engine
from app.core.logging import configure_logging
from app.jobs.scheduler import create_scheduler
from app.services.llm_service import LLMService

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


async def run_bot_polling(
    bot: Bot,
    dispatcher: Dispatcher,
    bot_settings: Settings,
) -> None:
    retry_delay = 5
    while True:
        try:
            await bot.get_me(request_timeout=15)
            await configure_bot_commands(
                bot,
                bot_settings.webapp_url,
                bot_settings.owner_telegram_id,
            )
            await bot.delete_webhook(drop_pending_updates=False, request_timeout=15)
            logger.info("Bot started in polling mode")
            await dispatcher.start_polling(
                bot,
                close_bot_session=False,
                handle_as_tasks=False,
                handle_signals=False,
            )
            return
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning(
                "Telegram connection failed; retrying in %s seconds: %s",
                retry_delay,
                error,
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)


async def configure_bot_webhook(
    bot: Bot,
    dispatcher: Dispatcher,
    bot_settings: Settings,
) -> None:
    retry_delay = 5
    webhook_url = f"{bot_settings.app_base_url.rstrip('/')}/api/telegram/webhook"
    while True:
        try:
            await bot.get_me(request_timeout=15)
            await configure_bot_commands(
                bot,
                bot_settings.webapp_url,
                bot_settings.owner_telegram_id,
            )
            await bot.set_webhook(
                webhook_url,
                secret_token=bot_settings.telegram_webhook_secret,
                allowed_updates=dispatcher.resolve_used_update_types(),
                drop_pending_updates=False,
                request_timeout=15,
            )
            logger.info("Bot webhook configured")
            return
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning(
                "Telegram webhook setup failed; retrying in %s seconds: %s",
                retry_delay,
                error,
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)


async def shutdown_polling(
    dispatcher: Dispatcher,
    polling_task: asyncio.Task[None],
) -> None:
    if not polling_task.done():
        try:
            await dispatcher.stop_polling()
        except RuntimeError:
            polling_task.cancel()
    with suppress(asyncio.CancelledError, Exception):
        await polling_task


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    logger.info("Application started")
    bot: Bot | None = None
    llm_service: LLMService | None = None
    dispatcher: Dispatcher | None = None
    telegram_task: asyncio.Task[None] | None = None
    scheduler: AsyncIOScheduler | None = None
    application.state.telegram_bot = None
    application.state.telegram_dispatcher = None

    try:
        if settings.telegram_bot_token and (
            settings.owner_telegram_id or settings.bot_allow_all_users
        ):
            bot = Bot(
                token=settings.telegram_bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
            dispatcher = create_dispatcher(settings)
            application.state.telegram_bot = bot
            application.state.telegram_dispatcher = dispatcher
            configured_llm = dispatcher["llm_service"]
            if isinstance(configured_llm, LLMService):
                llm_service = configured_llm
            if settings.bot_mode == "polling":
                telegram_task = asyncio.create_task(
                    run_bot_polling(bot, dispatcher, settings),
                    name="telegram-bot-supervisor",
                )
            else:
                telegram_task = asyncio.create_task(
                    configure_bot_webhook(bot, dispatcher, settings),
                    name="telegram-webhook-setup",
                )
            await asyncio.sleep(0)
            if settings.owner_telegram_id is not None:
                scheduler = create_scheduler(bot, settings)
                scheduler.start()
                logger.info("Scheduler started")
        elif settings.telegram_bot_token or settings.owner_telegram_id:
            logger.warning(
                "Bot not started: configure both token and owner ID, or explicitly enable "
                "BOT_ALLOW_ALL_USERS"
            )

        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        if telegram_task is not None and dispatcher is not None:
            if settings.bot_mode == "polling":
                await shutdown_polling(dispatcher, telegram_task)
            else:
                telegram_task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await telegram_task
        try:
            try:
                if llm_service is not None:
                    await llm_service.close()
            finally:
                if bot is not None:
                    await bot.session.close()
        finally:
            await engine.dispose()
            logger.info("Application stopped")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
