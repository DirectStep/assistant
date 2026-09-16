from typing import Literal

from aiogram.filters.callback_data import CallbackData


class TaskActionCallback(CallbackData, prefix="task"):
    action: Literal["complete", "delete"]
    task_id: int
