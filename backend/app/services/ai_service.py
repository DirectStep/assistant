from app.core.config import Settings
from app.services.gigachat_service import GigaChatService
from app.services.llm_service import LLMService

type AIService = LLMService | GigaChatService


def create_ai_service(settings: Settings) -> AIService | None:
    if settings.llm_provider == "gigachat":
        if not settings.gigachat_auth_key:
            return None
        return GigaChatService(
            settings.gigachat_auth_key,
            settings.gigachat_scope,
            settings.gigachat_task_model,
            settings.gigachat_news_model,
            verify_ssl=settings.gigachat_verify_ssl,
        )

    if not settings.openai_api_key:
        return None
    return LLMService(
        settings.openai_api_key,
        settings.openai_task_model,
        settings.openai_transcription_model,
        settings.openai_news_model,
    )
