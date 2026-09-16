from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import SourceType, TaskImportance, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.task_service import TaskService


def test_task_update_rejects_null_required_fields_and_naive_dates() -> None:
    with pytest.raises(ValidationError):
        TaskUpdate(status=None)
    with pytest.raises(ValidationError):
        TaskUpdate(title=None)
    with pytest.raises(ValidationError):
        TaskUpdate(due_at=datetime(2026, 9, 14, 9, 0))
    with pytest.raises(ValidationError):
        TaskCreate(
            title="Задача",
            source_type=SourceType.TEXT,
            due_at=datetime(2026, 9, 14, 9, 0),
        )


async def test_create_and_list_active_tasks(database_session: AsyncSession) -> None:
    service = TaskService(database_session, "Europe/Moscow")

    task = await service.create_task(
        1001,
        TaskCreate(
            title="  Подготовить презентацию  ",
            source_type=SourceType.TEXT,
            source_text="Подготовить презентацию",
            source_metadata={"message_id": 42},
        ),
    )

    assert task.title == "Подготовить презентацию"
    assert task.status == TaskStatus.INBOX
    assert task.importance == TaskImportance.NORMAL
    assert task.source_metadata == {"message_id": 42}
    assert await service.list_active_tasks(1001) == [task]
    assert await service.list_active_tasks(2002) == []


async def test_update_complete_and_delete_task(database_session: AsyncSession) -> None:
    service = TaskService(database_session, "Europe/Moscow")
    task = await service.create_task(
        1001,
        TaskCreate(title="Черновик", source_type=SourceType.TEXT),
    )

    updated = await service.update_task(
        task.id,
        1001,
        TaskUpdate(title="Финальная версия", importance=TaskImportance.IMPORTANT),
    )
    assert updated is not None
    assert updated.title == "Финальная версия"
    assert updated.importance == TaskImportance.IMPORTANT

    completed = await service.complete_task(task.id, 1001)
    assert completed is not None
    assert completed.status == TaskStatus.DONE
    assert completed.completed_at is not None
    assert await service.list_active_tasks(1001) == []

    assert await service.delete_task(task.id, 2002) is False
    assert await service.delete_task(task.id, 1001) is True
    assert await service.get_task(task.id, 1001) is None


async def test_today_includes_status_and_due_date(database_session: AsyncSession) -> None:
    service = TaskService(database_session, "Europe/Moscow")
    status_task = await service.create_task(
        1001,
        TaskCreate(
            title="Запланировано сегодня",
            source_type=SourceType.TEXT,
            status=TaskStatus.TODAY,
        ),
    )
    due_task = await service.create_task(
        1001,
        TaskCreate(
            title="Дедлайн сегодня",
            source_type=SourceType.TEXT,
            due_at=datetime(2026, 9, 14, 9, 0, tzinfo=UTC),
        ),
    )
    await service.create_task(
        1001,
        TaskCreate(
            title="Другая дата",
            source_type=SourceType.TEXT,
            due_at=datetime(2026, 9, 16, 9, 0, tzinfo=UTC),
        ),
    )

    tasks = await service.list_today_tasks(1001, date(2026, 9, 14))

    assert {task.id for task in tasks} == {status_task.id, due_task.id}


async def test_task_cannot_be_changed_by_another_user(database_session: AsyncSession) -> None:
    service = TaskService(database_session, "Europe/Moscow")
    task = await service.create_task(
        1001,
        TaskCreate(title="Личная задача", source_type=SourceType.TEXT),
    )

    assert await service.update_task(task.id, 2002, TaskUpdate(title="Чужая правка")) is None
    assert await service.complete_task(task.id, 2002) is None
    assert (await service.get_task(task.id, 1001)).title == "Личная задача"  # type: ignore[union-attr]
