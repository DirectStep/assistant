from urllib.parse import urlparse

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.bot.callbacks import TaskActionCallback


def task_actions_keyboard(task_id: int, delete_text: str = "Удалить") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Завершить",
                    callback_data=TaskActionCallback(action="complete", task_id=task_id).pack(),
                ),
                InlineKeyboardButton(
                    text=delete_text,
                    callback_data=TaskActionCallback(action="delete", task_id=task_id).pack(),
                ),
            ]
        ]
    )


def web_app_keyboard(url: str) -> InlineKeyboardMarkup | None:
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть приложение", web_app=WebAppInfo(url=url))]
        ]
    )


def morning_keyboard(url: str) -> InlineKeyboardMarkup | None:
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        return None
    base_url = url.rstrip("/")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть задачи",
                    web_app=WebAppInfo(url=f"{base_url}/tasks"),
                ),
                InlineKeyboardButton(
                    text="Сводки",
                    web_app=WebAppInfo(url=f"{base_url}/digests"),
                ),
            ]
        ]
    )
