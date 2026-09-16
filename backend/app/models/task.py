from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, BigInteger, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class SourceType(StrEnum):
    TEXT = "text"
    FORWARD = "forward"
    VOICE = "voice"
    WEBAPP = "webapp"


class TaskStatus(StrEnum):
    INBOX = "inbox"
    TODAY = "today"
    WEEK = "week"
    LATER = "later"
    DONE = "done"


class TaskImportance(StrEnum):
    NORMAL = "normal"
    IMPORTANT = "important"


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(
            SourceType,
            name="task_source_type",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    source_text: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(
            TaskStatus,
            name="task_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=TaskStatus.INBOX,
        nullable=False,
        index=True,
    )
    importance: Mapped[TaskImportance] = mapped_column(
        Enum(
            TaskImportance,
            name="task_importance",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=TaskImportance.NORMAL,
        nullable=False,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
