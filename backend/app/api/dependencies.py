import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, status
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas.auth import TelegramUser

INIT_DATA_MAX_AGE = timedelta(days=1)


def validate_telegram_init_data(
    init_data: str,
    bot_token: str,
    now: datetime | None = None,
) -> TelegramUser:
    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate initData fields")

    values = dict(pairs)
    received_hash = values.pop("hash", None)
    if not received_hash:
        raise ValueError("Missing initData hash")

    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("Invalid initData signature")

    current_time = now or datetime.now(UTC)
    try:
        auth_date = datetime.fromtimestamp(int(values["auth_date"]), tz=UTC)
    except (KeyError, ValueError, OSError) as error:
        raise ValueError("Invalid initData auth_date") from error
    if auth_date > current_time + timedelta(seconds=30):
        raise ValueError("initData auth_date is in the future")
    if current_time - auth_date > INIT_DATA_MAX_AGE:
        raise ValueError("Expired initData")

    try:
        return TelegramUser.model_validate_json(values["user"])
    except (KeyError, ValidationError, json.JSONDecodeError) as error:
        raise ValueError("Invalid initData user") from error


async def get_current_telegram_user(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> TelegramUser:
    if not authorization:
        if settings.dev_auth and settings.app_env != "production":
            user_id = settings.dev_telegram_user_id or settings.owner_telegram_id
            if user_id is not None:
                return TelegramUser(id=user_id, first_name="Development")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing initData")

    scheme, separator, init_data = authorization.partition(" ")
    if separator != " " or scheme.lower() != "tma" or not init_data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth scheme")
    if not settings.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram authentication is not configured",
        )

    try:
        user = validate_telegram_init_data(init_data, settings.telegram_bot_token)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired initData",
        ) from error

    if not settings.bot_allow_all_users and user.id != settings.owner_telegram_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return user
