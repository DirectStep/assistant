import logging
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskStatus
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate

logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self, session: AsyncSession, timezone: str) -> None:
        self.session = session
        self.repository = TaskRepository(session)
        self.timezone = ZoneInfo(timezone)

    async def create_task(self, telegram_user_id: int, data: TaskCreate) -> Task:
        task = await self.repository.create(telegram_user_id, data)
        if task.status == TaskStatus.DONE:
            task.completed_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(task)
        logger.info(
            "Task created", extra={"task_id": task.id, "telegram_user_id": telegram_user_id}
        )
        return task

    async def get_task(self, task_id: int, telegram_user_id: int) -> Task | None:
        return await self.repository.get(task_id, telegram_user_id)

    async def list_active_tasks(self, telegram_user_id: int, limit: int = 50) -> list[Task]:
        return await self.repository.list_active(telegram_user_id, limit)

    async def list_tasks(self, telegram_user_id: int) -> list[Task]:
        return await self.repository.list_all(telegram_user_id)

    async def list_today_tasks(
        self,
        telegram_user_id: int,
        target_date: date | None = None,
        limit: int = 50,
    ) -> list[Task]:
        local_date = target_date or datetime.now(self.timezone).date()
        local_start = datetime.combine(local_date, time.min, tzinfo=self.timezone)
        local_end = local_start + timedelta(days=1)
        return await self.repository.list_today(
            telegram_user_id,
            local_start.astimezone(UTC),
            local_end.astimezone(UTC),
            limit,
        )

    async def update_task(
        self,
        task_id: int,
        telegram_user_id: int,
        data: TaskUpdate,
    ) -> Task | None:
        task = await self.repository.get(task_id, telegram_user_id)
        if task is None:
            return None

        if data.status == TaskStatus.DONE and task.status != TaskStatus.DONE:
            task.completed_at = datetime.now(UTC)
        elif data.status is not None and data.status != TaskStatus.DONE:
            task.completed_at = None

        task = await self.repository.update(task, data)
        await self.session.commit()
        await self.session.refresh(task)
        if task.status == TaskStatus.DONE:
            logger.info(
                "Task completed",
                extra={"task_id": task.id, "telegram_user_id": telegram_user_id},
            )
        return task

    async def complete_task(self, task_id: int, telegram_user_id: int) -> Task | None:
        return await self.update_task(
            task_id,
            telegram_user_id,
            TaskUpdate(status=TaskStatus.DONE),
        )

    async def delete_task(self, task_id: int, telegram_user_id: int) -> bool:
        task = await self.repository.get(task_id, telegram_user_id)
        if task is None:
            return False

        await self.repository.delete(task)
        await self.session.commit()
        logger.info(
            "Task deleted",
            extra={"task_id": task_id, "telegram_user_id": telegram_user_id},
        )
        return True
