from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.settings import DEFAULT_NEWS_TOPICS, UserSettings
from app.repositories.settings_repository import SettingsRepository
from app.schemas.settings import UserSettingsUpdate


class SettingsService:
    def __init__(self, session: AsyncSession, app_settings: Settings) -> None:
        self.session = session
        self.app_settings = app_settings
        self.repository = SettingsRepository(session)

    async def get_or_create(self, telegram_user_id: int) -> UserSettings:
        user_settings = await self.repository.get(telegram_user_id)
        if user_settings is not None:
            return user_settings

        hour, minute = map(int, self.app_settings.daily_digest_time.split(":"))
        user_settings = UserSettings(
            telegram_user_id=telegram_user_id,
            daily_digest_time=time(hour, minute),
            timezone=self.app_settings.timezone,
            news_topics=list(DEFAULT_NEWS_TOPICS),
            news_max_articles=self.app_settings.news_max_articles,
        )
        await self.repository.create(user_settings)
        await self.session.commit()
        await self.session.refresh(user_settings)
        return user_settings

    async def update(
        self,
        telegram_user_id: int,
        data: UserSettingsUpdate,
    ) -> UserSettings:
        user_settings = await self.get_or_create(telegram_user_id)
        await self.repository.update(user_settings, data)
        await self.session.commit()
        await self.session.refresh(user_settings)
        return user_settings
