import logging
from datetime import datetime
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from app.models.task import SourceType, TaskImportance
from app.schemas.llm import ExtractedTask
from app.schemas.task import TaskCreate

logger = logging.getLogger(__name__)


class TaskAI(Protocol):
    async def extract_task_metadata(
        self,
        message: str,
        current_datetime: datetime,
        timezone: str,
    ) -> ExtractedTask: ...

    async def transcribe_voice(self, audio_path: Path) -> str: ...


class TranscriptionUnavailableError(RuntimeError):
    pass


def fallback_task_title(text: str) -> str | None:
    normalized = " ".join(text.split())
    if not normalized:
        return None
    if len(normalized) <= 500:
        return normalized
    return normalized[:497].rstrip() + "..."


class TaskIngestionService:
    def __init__(self, ai: TaskAI | None, timezone: str) -> None:
        self.ai = ai
        self.timezone = timezone

    async def build_task(
        self,
        text: str,
        source_type: SourceType,
        source_metadata: dict[str, object] | None = None,
        current_datetime: datetime | None = None,
    ) -> TaskCreate | None:
        fallback_title = fallback_task_title(text)
        if fallback_title is None:
            return None

        if self.ai is not None:
            try:
                now = current_datetime or datetime.now(ZoneInfo(self.timezone))
                extracted = await self.ai.extract_task_metadata(text, now, self.timezone)
                return TaskCreate(
                    title=extracted.title,
                    source_type=source_type,
                    source_text=text,
                    source_metadata=source_metadata,
                    importance=(
                        TaskImportance.IMPORTANT if extracted.important else TaskImportance.NORMAL
                    ),
                    due_at=extracted.due_at,
                )
            except Exception as error:
                logger.warning("Task metadata extraction failed; using original text: %s", error)

        return TaskCreate(
            title=fallback_title,
            source_type=source_type,
            source_text=text,
            source_metadata=source_metadata,
            importance=TaskImportance.NORMAL,
            due_at=None,
        )

    async def transcribe_voice(self, audio_path: Path) -> str:
        if self.ai is None:
            raise TranscriptionUnavailableError("AI provider is not configured")
        return await self.ai.transcribe_voice(audio_path)
