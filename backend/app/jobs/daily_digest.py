import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.keyboards import morning_keyboard
from app.core.config import Settings
from app.core.database import async_session_factory
from app.models.task import Task, TaskStatus
from app.repositories.digest_repository import DigestRepository
from app.services.digest_generation_service import generate_digest_for_user
from app.services.settings_service import SettingsService
from app.services.task_service import TaskService

logger = logging.getLogger(__name__)

RUSSIAN_MONTHS = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


async def daily_digest_job(
    bot: Bot,
    settings: Settings,
    *,
    session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
    now: datetime | None = None,
    force: bool = False,
) -> bool:
    owner_id = settings.owner_telegram_id
    if owner_id is None:
        logger.warning("Daily digest skipped: OWNER_TELEGRAM_ID is not configured")
        return False

    async with session_factory() as session:
        user_settings = await SettingsService(session, settings).get_or_create(owner_id)
        timezone = ZoneInfo(user_settings.timezone)
        local_now = (now or datetime.now(timezone)).astimezone(timezone)
        digest_date = local_now.date()
        scheduled_time = user_settings.daily_digest_time
        scheduled_at = datetime.combine(digest_date, scheduled_time, tzinfo=timezone)
        if not force:
            already_sent = user_settings.last_daily_digest_sent_on == digest_date
            outside_delivery_window = not scheduled_at <= local_now < scheduled_at + timedelta(
                hours=2
            )
            if already_sent or outside_delivery_window:
                return False

        task_service = TaskService(session, user_settings.timezone)
        tasks = await task_service.list_active_tasks(owner_id, limit=500)
        news_ready = False
        pdf_path: Path | None = None
        try:
            await generate_digest_for_user(session, settings, user_settings, digest_date)
            digest = await DigestRepository(session).get_by_date(digest_date)
            if digest and digest.pdf_path and Path(digest.pdf_path).is_file():
                pdf_path = Path(digest.pdf_path)
                news_ready = True
        except Exception:
            logger.exception("Daily news generation failed")

        text = build_morning_message(tasks, digest_date, timezone, news_ready)
        await _retry(
            lambda: bot.send_message(
                owner_id,
                text,
                reply_markup=morning_keyboard(settings.webapp_url),
            )
        )
        if pdf_path is not None:
            try:
                await _retry(
                    lambda: bot.send_document(
                        owner_id,
                        FSInputFile(pdf_path, filename=pdf_path.name),
                    )
                )
            except Exception:
                logger.exception("Daily digest PDF delivery failed")
                await bot.send_message(owner_id, "PDF не удалось отправить. Попробуй /news позже.")

        user_settings.last_daily_digest_sent_on = digest_date
        await session.commit()
        logger.info("Daily digest sent", extra={"digest_date": digest_date.isoformat()})
        return True


def build_morning_message(
    tasks: list[Task],
    digest_date: date,
    timezone: ZoneInfo,
    news_ready: bool,
) -> str:
    today: list[Task] = []
    overdue: list[Task] = []
    week_count = 0
    for task in tasks:
        due_date = _local_due_date(task, timezone)
        if due_date is not None and due_date < digest_date:
            overdue.append(task)
        elif task.status == TaskStatus.TODAY or due_date == digest_date:
            today.append(task)
        elif task.status == TaskStatus.WEEK or (
            due_date is not None and 0 < (due_date - digest_date).days <= 7
        ):
            week_count += 1

    lines = [
        f"<b>{digest_date.day} {RUSSIAN_MONTHS[digest_date.month]}</b>",
        "",
        "<b>Задачи</b>",
        "",
        "<b>Сегодня:</b>",
        *_task_lines(today),
        "",
        "<b>Просрочено:</b>",
        *_task_lines(overdue),
        "",
        f"<b>На неделе:</b> {week_count}",
        "",
        "Новостная сводка готова."
        if news_ready
        else "Новостную сводку сегодня сформировать не удалось.",
    ]
    return "\n".join(lines)


def _task_lines(tasks: list[Task], visible_limit: int = 10) -> list[str]:
    if not tasks:
        return ["—"]
    lines = [
        f"{position}. {escape(task.title)}"
        for position, task in enumerate(tasks[:visible_limit], 1)
    ]
    if len(tasks) > visible_limit:
        lines.append(f"Ещё: {len(tasks) - visible_limit}")
    return lines


def _local_due_date(task: Task, timezone: ZoneInfo) -> date | None:
    if task.due_at is None:
        return None
    due_at = task.due_at
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    return due_at.astimezone(timezone).date()


async def _retry[T](factory: Callable[[], Awaitable[T]], attempts: int = 3) -> T:
    for attempt in range(attempts):
        try:
            return await factory()
        except Exception:
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(2**attempt)
    raise RuntimeError("unreachable")
