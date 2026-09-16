from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ExtractedTask(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    due_at: datetime | None
    important: bool

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        title = " ".join(value.split())
        if not title:
            raise ValueError("Extracted task title cannot be empty")
        return title
