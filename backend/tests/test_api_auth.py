import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException

from app.api.dependencies import get_current_telegram_user, validate_telegram_init_data
from app.core.config import Settings


def signed_init_data(bot_token: str, user_id: int, auth_date: datetime) -> str:
    values = {
        "auth_date": str(int(auth_date.timestamp())),
        "query_id": "AAE-test",
        "user": json.dumps(
            {"id": user_id, "first_name": "Стёпа", "username": "KryGerMan"},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    return urlencode(values)


def test_valid_telegram_init_data_returns_signed_user() -> None:
    now = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    init_data = signed_init_data("test-token", 1781530480, now)

    user = validate_telegram_init_data(init_data, "test-token", now)

    assert user.id == 1781530480
    assert user.username == "KryGerMan"


def test_telegram_init_data_rejects_wrong_signature() -> None:
    now = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    init_data = signed_init_data("test-token", 1781530480, now)

    with pytest.raises(ValueError, match="signature"):
        validate_telegram_init_data(init_data, "different-token", now)


def test_telegram_init_data_rejects_expired_payload() -> None:
    now = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
    init_data = signed_init_data("test-token", 1781530480, now - timedelta(days=2))

    with pytest.raises(ValueError, match="Expired"):
        validate_telegram_init_data(init_data, "test-token", now)


async def test_api_auth_rejects_signed_non_owner() -> None:
    init_data = signed_init_data("test-token", 2002, datetime.now(UTC))
    settings = Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite://",
        telegram_bot_token="test-token",
        owner_telegram_id=1001,
        bot_allow_all_users=False,
    )

    with pytest.raises(HTTPException) as error:
        await get_current_telegram_user(settings, f"tma {init_data}")

    assert error.value.status_code == 403


async def test_dev_auth_uses_configured_development_user() -> None:
    settings = Settings(
        _env_file=None,
        app_env="development",
        database_url="sqlite+aiosqlite://",
        dev_auth=True,
        dev_telegram_user_id=1781530480,
    )

    user = await get_current_telegram_user(settings, None)

    assert user.id == 1781530480
