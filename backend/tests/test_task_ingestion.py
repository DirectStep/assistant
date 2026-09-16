from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.models.task import SourceType, TaskImportance
from app.schemas.llm import ExtractedTask
from app.services.llm_service import LLMResponseError, LLMService
from app.services.task_ingestion_service import (
    TaskIngestionService,
    TranscriptionUnavailableError,
    fallback_task_title,
)


class FakeTaskAI:
    def __init__(self, extracted: ExtractedTask) -> None:
        self.extracted = extracted
        self.request: tuple[str, datetime, str] | None = None

    async def extract_task_metadata(
        self,
        message: str,
        current_datetime: datetime,
        timezone: str,
    ) -> ExtractedTask:
        self.request = (message, current_datetime, timezone)
        return self.extracted

    async def transcribe_voice(self, audio_path: Path) -> str:
        return "Отправить отчёт завтра"


class FailingTaskAI(FakeTaskAI):
    async def extract_task_metadata(
        self,
        message: str,
        current_datetime: datetime,
        timezone: str,
    ) -> ExtractedTask:
        raise RuntimeError("OpenAI unavailable")


class InvalidTaskAI(FakeTaskAI):
    async def extract_task_metadata(
        self,
        message: str,
        current_datetime: datetime,
        timezone: str,
    ) -> ExtractedTask:
        return ExtractedTask.model_construct(title="   ", due_at=None, important=False)


async def test_ingestion_uses_structured_metadata() -> None:
    due_at = datetime(2026, 9, 15, 9, 0, tzinfo=UTC)
    ai = FakeTaskAI(ExtractedTask(title="Отправить отчёт", due_at=due_at, important=True))
    service = TaskIngestionService(ai, "Europe/Moscow")
    now = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)

    task = await service.build_task(
        "Завтра срочно отправить отчёт",
        SourceType.TEXT,
        current_datetime=now,
    )

    assert task is not None
    assert task.title == "Отправить отчёт"
    assert task.due_at == due_at
    assert task.importance == TaskImportance.IMPORTANT
    assert task.source_text == "Завтра срочно отправить отчёт"
    assert ai.request == ("Завтра срочно отправить отчёт", now, "Europe/Moscow")


async def test_ingestion_falls_back_without_losing_text() -> None:
    original = "x" * 700
    ai = FailingTaskAI(ExtractedTask(title="unused", due_at=None, important=False))
    service = TaskIngestionService(ai, "Europe/Moscow")

    task = await service.build_task(original, SourceType.FORWARD, {"source": "channel"})

    assert task is not None
    assert task.title == fallback_task_title(original)
    assert task.source_text == original
    assert task.source_metadata == {"source": "channel"}
    assert task.due_at is None


def test_extracted_task_rejects_whitespace_title() -> None:
    with pytest.raises(ValidationError):
        ExtractedTask(title="   ", due_at=None, important=False)


async def test_ingestion_falls_back_when_ai_payload_is_invalid() -> None:
    ai = InvalidTaskAI(ExtractedTask(title="unused", due_at=None, important=False))
    service = TaskIngestionService(ai, "Europe/Moscow")

    task = await service.build_task("  Исходная задача  ", SourceType.TEXT)

    assert task is not None
    assert task.title == "Исходная задача"
    assert task.source_text == "  Исходная задача  "


async def test_voice_requires_openai_configuration(tmp_path: Path) -> None:
    service = TaskIngestionService(None, "Europe/Moscow")

    with pytest.raises(TranscriptionUnavailableError):
        await service.transcribe_voice(tmp_path / "voice.ogg")


async def test_llm_service_normalizes_naive_deadline_to_utc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = LLMService("test-key", "task-model", "voice-model")
    parsed = ExtractedTask(
        title="В пятницу отправить отчёт",
        due_at=datetime(2026, 9, 18, 18, 0),
        important=False,
    )
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))
    monkeypatch.setattr(service.client.responses, "parse", parse)

    result = await service.extract_task_metadata(
        "В пятницу отправить отчёт",
        datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        "Europe/Moscow",
    )

    assert result.due_at == datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
    assert parse.await_count == 1
    await service.client.close()


async def test_llm_service_rejects_empty_structured_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = LLMService("test-key", "task-model", "voice-model")
    monkeypatch.setattr(
        service.client.responses,
        "parse",
        AsyncMock(return_value=SimpleNamespace(output_parsed=None)),
    )

    with pytest.raises(LLMResponseError):
        await service.extract_task_metadata(
            "Задача",
            datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            "Europe/Moscow",
        )
    await service.client.close()


async def test_llm_service_transcribes_voice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"fake ogg")
    service = LLMService("test-key", "task-model", "voice-model")
    create = AsyncMock(return_value=SimpleNamespace(text="  Отправить таблицу  "))
    monkeypatch.setattr(service.client.audio.transcriptions, "create", create)

    assert await service.transcribe_voice(audio_path) == "Отправить таблицу"
    assert create.await_count == 1
    await service.client.close()
