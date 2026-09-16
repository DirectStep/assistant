from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_telegram_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.schemas.auth import TelegramUser
from app.schemas.settings import UserSettingsRead, UserSettingsUpdate
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])
CurrentUser = Annotated[TelegramUser, Depends(get_current_telegram_user)]
Session = Annotated[AsyncSession, Depends(get_session)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("", response_model=UserSettingsRead)
async def get_user_settings(
    user: CurrentUser,
    session: Session,
    settings: AppSettings,
) -> UserSettingsRead:
    value = await SettingsService(session, settings).get_or_create(user.id)
    return UserSettingsRead.model_validate(value)


@router.patch("", response_model=UserSettingsRead)
async def update_user_settings(
    data: UserSettingsUpdate,
    user: CurrentUser,
    session: Session,
    settings: AppSettings,
) -> UserSettingsRead:
    value = await SettingsService(session, settings).update(user.id, data)
    return UserSettingsRead.model_validate(value)
