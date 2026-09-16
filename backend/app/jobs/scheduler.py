from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]

from app.core.config import Settings
from app.jobs.cleanup import cleanup_job
from app.jobs.daily_digest import daily_digest_job


def create_scheduler(bot: Bot, settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        daily_digest_job,
        CronTrigger(second=0, timezone=settings.timezone),
        id="daily_digest_job",
        kwargs={"bot": bot, "settings": settings},
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=50,
    )
    scheduler.add_job(
        cleanup_job,
        CronTrigger(hour=3, minute=15, timezone=settings.timezone),
        id="cleanup_job",
        kwargs={"settings": settings},
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    return scheduler
