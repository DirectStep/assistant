import asyncio
import json
import mimetypes
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel

from app.schemas.llm import ExtractedTask
from app.schemas.news import (
    DigestIntro,
    NewsArticleInput,
    NewsScore,
    NewsScoreBatch,
    NewsSummary,
    NewsSummaryBatch,
)
from app.services.llm_service import (
    DIGEST_INTRO_PROMPT,
    NEWS_SCORING_PROMPT,
    NEWS_SUMMARY_PROMPT,
    TASK_EXTRACTION_PROMPT,
    LLMResponseError,
)

ParsedModel = TypeVar("ParsedModel", bound=BaseModel)


class GigaChatService:
    def __init__(
        self,
        auth_key: str,
        scope: str,
        task_model: str,
        news_model: str | None = None,
        *,
        verify_ssl: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.auth_key = auth_key.removeprefix("Basic ").strip()
        self.scope = scope
        self.task_model = task_model
        self.news_model = news_model or task_model
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=15.0),
            verify=verify_ssl,
            transport=transport,
        )
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    async def close(self) -> None:
        await self.client.aclose()

    async def _get_access_token(self, *, force_refresh: bool = False) -> str:
        if (
            not force_refresh
            and self._access_token
            and time.time() < self._access_token_expires_at - 60
        ):
            return self._access_token

        async with self._token_lock:
            if (
                not force_refresh
                and self._access_token
                and time.time() < self._access_token_expires_at - 60
            ):
                return self._access_token

            response = await self.client.post(
                "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
                headers={
                    "Authorization": f"Basic {self.auth_key}",
                    "RqUID": str(uuid4()),
                },
                data={"scope": self.scope},
            )
            response.raise_for_status()
            payload = response.json()
            token = payload.get("access_token")
            if not isinstance(token, str) or not token:
                raise LLMResponseError("GigaChat returned no access token")

            expires_at = float(payload.get("expires_at", time.time() + 1800))
            if expires_at > 100_000_000_000:
                expires_at /= 1000
            self._access_token = token
            self._access_token_expires_at = expires_at
            return token

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        request_headers = kwargs.pop("headers", {})
        for attempt in range(2):
            token = await self._get_access_token(force_refresh=attempt == 1)
            headers = {"Authorization": f"Bearer {token}", **request_headers}
            response = await self.client.request(
                method,
                f"https://api.giga.chat/v1{path}",
                headers=headers,
                **kwargs,
            )
            if response.status_code != httpx.codes.UNAUTHORIZED or attempt == 1:
                response.raise_for_status()
                return response
        raise LLMResponseError("GigaChat authorization failed")

    async def _chat_json(
        self,
        *,
        model: str,
        instructions: str,
        user_input: str,
        output_model: type[ParsedModel],
    ) -> ParsedModel:
        schema = output_model.model_json_schema()
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": instructions},
                {
                    "role": "user",
                    "content": (
                        f"{user_input}\n\nВерни только JSON по этой схеме:\n"
                        f"{json.dumps(schema, ensure_ascii=False)}"
                    ),
                },
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_schema", "schema": schema, "strict": True},
        }
        try:
            response = await self._request("POST", "/chat/completions", json=payload)
        except httpx.HTTPStatusError as error:
            if error.response.status_code not in {
                httpx.codes.BAD_REQUEST,
                httpx.codes.UNPROCESSABLE_ENTITY,
            }:
                raise
            payload.pop("response_format")
            response = await self._request("POST", "/chat/completions", json=payload)

        try:
            content = response.json()["choices"][0]["message"]["content"]
            return output_model.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise LLMResponseError("GigaChat returned invalid structured output") from error

    async def extract_task_metadata(
        self,
        message: str,
        current_datetime: datetime,
        timezone: str,
    ) -> ExtractedTask:
        extracted = await self._chat_json(
            model=self.task_model,
            instructions=TASK_EXTRACTION_PROMPT,
            user_input=(
                f"Current datetime: {current_datetime.isoformat()}\n"
                f"Timezone: {timezone}\n"
                f"User message:\n{message}"
            ),
            output_model=ExtractedTask,
        )
        due_at = extracted.due_at
        if due_at is not None:
            if due_at.tzinfo is None or due_at.utcoffset() is None:
                due_at = due_at.replace(tzinfo=ZoneInfo(timezone))
            extracted = extracted.model_copy(update={"due_at": due_at.astimezone(UTC)})
        return extracted

    async def transcribe_voice(self, audio_path: Path) -> str:
        mime_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
        with audio_path.open("rb") as audio_file:
            uploaded = await self._request(
                "POST",
                "/files",
                files={"file": (audio_path.name, audio_file, mime_type)},
                data={"purpose": "general"},
            )
        try:
            file_id = uploaded.json()["id"]
        except (KeyError, TypeError, ValueError) as error:
            raise LLMResponseError("GigaChat returned no uploaded file ID") from error

        try:
            response = await self._request(
                "POST",
                "/chat/completions",
                json={
                    "model": self.task_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Расшифруй голосовое сообщение дословно. "
                                "Верни только распознанный текст без комментариев."
                            ),
                            "attachments": [file_id],
                        }
                    ],
                    "temperature": 0,
                },
            )
            try:
                content = response.json()["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError, ValueError) as error:
                raise LLMResponseError("GigaChat returned invalid transcription") from error
            if not isinstance(content, str):
                raise LLMResponseError("GigaChat returned invalid transcription")
            text = content.strip()
            if not text:
                raise LLMResponseError("GigaChat returned an empty transcription")
            return text
        finally:
            try:
                await self._request("POST", f"/files/{file_id}/delete")
            except (httpx.HTTPError, LLMResponseError):
                pass

    async def score_news_relevance(
        self,
        articles: list[NewsArticleInput],
        interests: list[str],
    ) -> list[NewsScore]:
        payload = [
            {
                "index": index,
                "title": article.title,
                "source": article.source,
                "category": article.category,
                "description": (article.raw_description or "")[:1500],
            }
            for index, article in enumerate(articles)
        ]
        parsed = await self._chat_json(
            model=self.news_model,
            instructions=NEWS_SCORING_PROMPT,
            user_input=json.dumps(
                {"interests": interests, "articles": payload},
                ensure_ascii=False,
            ),
            output_model=NewsScoreBatch,
        )
        return parsed.root

    async def summarize_news(self, articles: list[NewsArticleInput]) -> list[NewsSummary]:
        payload = [
            {
                "index": index,
                "title": article.title,
                "source": article.source,
                "description": (article.raw_description or "")[:2000],
            }
            for index, article in enumerate(articles)
        ]
        parsed = await self._chat_json(
            model=self.news_model,
            instructions=NEWS_SUMMARY_PROMPT,
            user_input=json.dumps(payload, ensure_ascii=False),
            output_model=NewsSummaryBatch,
        )
        return parsed.root

    async def build_digest_intro(self, articles: list[NewsSummary]) -> DigestIntro:
        return await self._chat_json(
            model=self.news_model,
            instructions=DIGEST_INTRO_PROMPT,
            user_input=json.dumps(
                [
                    {"headline": article.headline, "summary": article.summary}
                    for article in articles[:5]
                ],
                ensure_ascii=False,
            ),
            output_model=DigestIntro,
        )
