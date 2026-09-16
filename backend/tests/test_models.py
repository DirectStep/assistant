from typing import cast

from sqlalchemy import Enum
from sqlalchemy.orm import configure_mappers

from app.models import (
    DailyDigest,
    DigestStatus,
    SourceType,
    Task,
    TaskImportance,
    TaskStatus,
    UserSettings,
)


def test_all_model_relationships_are_configurable() -> None:
    configure_mappers()


def test_database_enums_store_public_values() -> None:
    source_type = cast(Enum, Task.__table__.c.source_type.type)
    task_status = cast(Enum, Task.__table__.c.status.type)
    task_importance = cast(Enum, Task.__table__.c.importance.type)
    digest_status = cast(Enum, DailyDigest.__table__.c.status.type)

    assert source_type.enums == [item.value for item in SourceType]
    assert task_status.enums == [item.value for item in TaskStatus]
    assert task_importance.enums == [item.value for item in TaskImportance]
    assert digest_status.enums == [item.value for item in DigestStatus]

    assert source_type.create_constraint is True
    assert task_status.create_constraint is True
    assert task_importance.create_constraint is True
    assert digest_status.create_constraint is True


def test_telegram_user_id_is_not_generated_by_database() -> None:
    assert UserSettings.__table__.c.telegram_user_id.autoincrement is False
