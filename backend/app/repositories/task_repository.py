from datetime import datetime

from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskImportance, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, telegram_user_id: int, data: TaskCreate) -> Task:
        task = Task(telegram_user_id=telegram_user_id, **data.model_dump())
        self.session.add(task)
        await self.session.flush()
        return task

    async def get(self, task_id: int, telegram_user_id: int) -> Task | None:
        task: Task | None = await self.session.scalar(
            select(Task).where(Task.id == task_id, Task.telegram_user_id == telegram_user_id)
        )
        return task

    async def list_active(self, telegram_user_id: int, limit: int = 50) -> list[Task]:
        result = await self.session.scalars(
            select(Task)
            .where(Task.telegram_user_id == telegram_user_id, Task.status != TaskStatus.DONE)
            .order_by(
                case((Task.importance == TaskImportance.IMPORTANT, 0), else_=1),
                Task.due_at.asc().nulls_last(),
                Task.created_at.asc(),
            )
            .limit(limit)
        )
        return list(result)

    async def list_all(self, telegram_user_id: int) -> list[Task]:
        status_order = case(
            (Task.status == TaskStatus.INBOX, 0),
            (Task.status == TaskStatus.TODAY, 1),
            (Task.status == TaskStatus.WEEK, 2),
            (Task.status == TaskStatus.LATER, 3),
            else_=4,
        )
        result = await self.session.scalars(
            select(Task)
            .where(Task.telegram_user_id == telegram_user_id)
            .order_by(
                status_order,
                case((Task.importance == TaskImportance.IMPORTANT, 0), else_=1),
                Task.due_at.asc().nulls_last(),
                Task.created_at.desc(),
            )
        )
        return list(result)

    async def list_today(
        self,
        telegram_user_id: int,
        day_start: datetime,
        day_end: datetime,
        limit: int,
    ) -> list[Task]:
        result = await self.session.scalars(
            select(Task)
            .where(
                Task.telegram_user_id == telegram_user_id,
                Task.status != TaskStatus.DONE,
                or_(
                    Task.status == TaskStatus.TODAY,
                    (Task.due_at >= day_start) & (Task.due_at < day_end),
                ),
            )
            .order_by(
                case((Task.importance == TaskImportance.IMPORTANT, 0), else_=1),
                Task.due_at.asc().nulls_last(),
                Task.created_at.asc(),
            )
            .limit(limit)
        )
        return list(result)

    async def update(self, task: Task, data: TaskUpdate) -> Task:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(task, field, value)
        await self.session.flush()
        return task

    async def delete(self, task: Task) -> None:
        await self.session.delete(task)
        await self.session.flush()
