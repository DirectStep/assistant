import os
import time
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.jobs.cleanup import _remove_stale_temporary_pdfs
from app.jobs.daily_digest import build_morning_message, daily_digest_job
from app.jobs.scheduler import create_scheduler
from app.models.digest import DailyDigest, DigestStatus
from app.models.task import SourceType, Task, TaskStatus
from app.schemas.news import DigestPreview


def test_morning_message_groups_today_overdue_and_week_tasks() -> None:
    timezone = ZoneInfo("Europe/Moscow")
    target_date = date(2026, 9, 14)
    tasks = [
        Task(
            title="Сегодня",
            telegram_user_id=1,
            source_type=SourceType.TEXT,
            status=TaskStatus.TODAY,
        ),
        Task(
            title="Просрочено",
            telegram_user_id=1,
            source_type=SourceType.TEXT,
            due_at=datetime(2026, 9, 13, 10, tzinfo=timezone).astimezone(UTC),
        ),
        Task(
            title="На неделе",
            telegram_user_id=1,
            source_type=SourceType.TEXT,
            status=TaskStatus.WEEK,
        ),
    ]

    text = build_morning_message(tasks, target_date, timezone, news_ready=True)

    assert "1. Сегодня" in text
    assert "1. Просрочено" in text
    assert "<b>На неделе:</b> 1" in text
    assert "Новостная сводка готова." in text


async def test_daily_job_sends_once_and_persists_marker(
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    owner_id = 1781530480
    pdf_path = tmp_path / "daily_digest_2026-09-14.pdf"
    pdf_path.write_bytes(b"%PDF-test")
    session_factory = async_sessionmaker(database_session.bind, expire_on_commit=False)
    generated = 0

    async def fake_generate(
        session: AsyncSession,
        settings: Settings,
        user_settings: object,
        digest_date: date,
    ) -> DigestPreview:
        nonlocal generated
        generated += 1
        session.add(
            DailyDigest(
                date=digest_date,
                status=DigestStatus.COMPLETED,
                pdf_path=str(pdf_path),
                articles=[],
            )
        )
        await session.commit()
        return DigestPreview(
            generated_at=datetime.now(UTC),
            intro="",
            articles=[],
            empty_categories=[],
            fetched_count=0,
            deduplicated_count=0,
        )

    monkeypatch.setattr("app.jobs.daily_digest.generate_digest_for_user", fake_generate)
    bot = SimpleNamespace(send_message=AsyncMock(), send_document=AsyncMock())
    settings = Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite://",
        owner_telegram_id=owner_id,
        daily_digest_time="08:30",
        digest_output_dir=tmp_path,
        webapp_url="https://assistant.example.com",
    )
    now = datetime(2026, 9, 14, 8, 30, tzinfo=ZoneInfo("Europe/Moscow"))

    first = await daily_digest_job(
        cast(Bot, bot),
        settings,
        session_factory=session_factory,
        now=now,
    )
    second = await daily_digest_job(
        cast(Bot, bot),
        settings,
        session_factory=session_factory,
        now=now,
    )

    assert first is True
    assert second is False
    assert generated == 1
    assert bot.send_message.await_count == 1
    assert bot.send_document.await_count == 1


def test_scheduler_registers_required_jobs() -> None:
    settings = Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite://",
        owner_telegram_id=1,
    )
    scheduler = create_scheduler(cast(Bot, SimpleNamespace()), settings)

    assert {job.id for job in scheduler.get_jobs()} == {"daily_digest_job", "cleanup_job"}


def test_cleanup_only_removes_old_temporary_pdfs(tmp_path: Path) -> None:
    stale = tmp_path / "stale.tmp.pdf"
    fresh = tmp_path / "fresh.tmp.pdf"
    real = tmp_path / "daily_digest_2026-09-14.pdf"
    for path in (stale, fresh, real):
        path.write_bytes(b"pdf")
    old_timestamp = time.time() - 90_000
    os.utime(stale, (old_timestamp, old_timestamp))

    removed = _remove_stale_temporary_pdfs(tmp_path)

    assert removed == 1
    assert not stale.exists()
    assert fresh.exists()
    assert real.exists()
