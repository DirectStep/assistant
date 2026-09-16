import secrets
from typing import Annotated, cast

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from app.core.config import Settings, get_settings

router = APIRouter(prefix="/telegram", tags=["telegram"])
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.post("/webhook", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
async def telegram_webhook(
    request: Request,
    settings: AppSettings,
    secret_token: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> Response:
    if settings.bot_mode != "webhook":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    expected_secret = settings.telegram_webhook_secret
    if expected_secret is None or secret_token is None or not secrets.compare_digest(
        secret_token, expected_secret
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")

    bot = cast(Bot | None, getattr(request.app.state, "telegram_bot", None))
    dispatcher = cast(Dispatcher | None, getattr(request.app.state, "telegram_dispatcher", None))
    if bot is None or dispatcher is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot is unavailable",
        )

    try:
        update = Update.model_validate(await request.json(), context={"bot": bot})
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Telegram update",
        ) from error
    await dispatcher.feed_update(bot, update)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
