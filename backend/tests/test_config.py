import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_accept_empty_optional_secrets() -> None:
    settings = Settings(
        telegram_bot_token="",
        openai_api_key="",
        owner_telegram_id="",
    )

    assert settings.telegram_bot_token is None
    assert settings.openai_api_key is None
    assert settings.owner_telegram_id is None


def test_news_limit_is_restricted() -> None:
    with pytest.raises(ValidationError):
        Settings(news_max_articles=21)


def test_owner_id_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(owner_telegram_id=0)


def test_database_url_is_built_with_encoded_credentials() -> None:
    settings = Settings(
        database_url="",
        postgres_user="user@example.com",
        postgres_password="p@ss%word",
        postgres_db="assistant_db",
        postgres_host="localhost",
    )

    assert settings.database_url == (
        "postgresql+asyncpg://user%40example.com:p%40ss%25word@localhost:5432/assistant_db"
    )


def test_database_name_rejects_unsafe_characters() -> None:
    with pytest.raises(ValidationError):
        Settings(postgres_db="assistant db")


def test_timezone_must_be_valid() -> None:
    with pytest.raises(ValidationError):
        Settings(timezone="Europe/Moscow-typo")


def test_daily_digest_time_must_be_valid() -> None:
    with pytest.raises(ValidationError):
        Settings(daily_digest_time="25:90")


def test_explicit_database_url_takes_priority() -> None:
    url = "postgresql+asyncpg://custom:encoded%40password@database:5432/custom"

    assert Settings(database_url=url).database_url == url


def test_production_rejects_dev_auth() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+asyncpg://user:pass@db/app",
            telegram_bot_token="test-token",
            owner_telegram_id=1001,
            dev_auth=True,
        )


def test_production_rejects_allow_all_users() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+asyncpg://user:pass@db/app",
            telegram_bot_token="test-token",
            owner_telegram_id=1001,
            bot_allow_all_users=True,
        )


def test_production_requires_bot_credentials() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+asyncpg://user:pass@db/app",
        )


def test_production_accepts_secure_webhook_configuration() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        database_url="postgresql+asyncpg://user:pass@db/app",
        telegram_bot_token="test-token",
        owner_telegram_id=1001,
        bot_mode="webhook",
        telegram_webhook_secret="safe_webhook_secret_1234567890",
        app_base_url="https://assistant.example.com",
        webapp_url="https://assistant.example.com",
    )

    assert settings.bot_mode == "webhook"


def test_production_webhook_requires_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+asyncpg://user:pass@db/app",
            telegram_bot_token="test-token",
            owner_telegram_id=1001,
            bot_mode="webhook",
            app_base_url="https://assistant.example.com",
            webapp_url="https://assistant.example.com",
        )
