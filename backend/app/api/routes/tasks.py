from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_telegram_user
from app.core.database import get_session
from app.models.task import SourceType
from app.schemas.auth import TelegramUser
from app.schemas.task import TaskCreate, TaskMove, TaskRead, TaskUpdate, WebTaskCreate
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])
CurrentUser = Annotated[TelegramUser, Depends(get_current_telegram_user)]
Session = Annotated[AsyncSession, Depends(get_session)]


def task_service(session: AsyncSession) -> TaskService:
    from app.core.config import get_settings

    return TaskService(session, get_settings().timezone)


@router.get("", response_model=list[TaskRead])
async def list_tasks(user: CurrentUser, session: Session) -> list[TaskRead]:
    tasks = await task_service(session).list_tasks(user.id)
    return [TaskRead.model_validate(task) for task in tasks]


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(data: WebTaskCreate, user: CurrentUser, session: Session) -> TaskRead:
    task = await task_service(session).create_task(
        user.id,
        TaskCreate(
            **data.model_dump(),
            source_type=SourceType.WEBAPP,
            source_text=data.title,
        ),
    )
    return TaskRead.model_validate(task)


async def require_task(task_id: int, user: TelegramUser, service: TaskService) -> TaskRead:
    task = await service.get_task(task_id, user.id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskRead.model_validate(task)


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(task_id: int, user: CurrentUser, session: Session) -> TaskRead:
    return await require_task(task_id, user, task_service(session))


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int,
    data: TaskUpdate,
    user: CurrentUser,
    session: Session,
) -> TaskRead:
    task = await task_service(session).update_task(task_id, user.id, data)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskRead.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, user: CurrentUser, session: Session) -> Response:
    deleted = await task_service(session).delete_task(task_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/complete", response_model=TaskRead)
async def complete_task(task_id: int, user: CurrentUser, session: Session) -> TaskRead:
    task = await task_service(session).complete_task(task_id, user.id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskRead.model_validate(task)


@router.post("/{task_id}/move", response_model=TaskRead)
async def move_task(
    task_id: int,
    data: TaskMove,
    user: CurrentUser,
    session: Session,
) -> TaskRead:
    task = await task_service(session).update_task(
        task_id,
        user.id,
        TaskUpdate(status=data.status),
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskRead.model_validate(task)
