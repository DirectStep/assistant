from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import UserSettings
from app.schemas.settings import UserSettingsUpdate


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, telegram_user_id: int) -> UserSettings | None:
        return await self.session.get(UserSettings, telegram_user_id)

    async def create(self, settings: UserSettings) -> UserSettings:
        self.session.add(settings)
        await self.session.flush()
        return settings

    async def update(
        self,
        settings: UserSettings,
        data: UserSettingsUpdate,
    ) -> UserSettings:
        for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
            setattr(settings, field, value)
        await self.session.flush()
        return settings
