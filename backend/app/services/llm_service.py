import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI

from app.schemas.llm import ExtractedTask
from app.schemas.news import (
    DigestIntro,
    NewsArticleInput,
    NewsScore,
    NewsScoreBatch,
    NewsSummary,
    NewsSummaryBatch,
)

TASK_EXTRACTION_PROMPT = """Ты извлекаешь информацию из задачи пользователя.

Ничего не придумывай.
Если дедлайн явно не указан — due_at должен быть null.
Если пользователь явно не говорит, что задача важная или срочная — important=false.
Сохраняй смысл исходного сообщения. Не добавляй проект, категорию, длительность или статус.
Если указана относительная дата, вычисли абсолютную дату в переданном часовом поясе.
"""

NEWS_SCORING_PROMPT = """Ты оцениваешь релевантность реальных новостных материалов.

Для каждого входного элемента верни ровно один результат с тем же index.
Оцени от 0 до 100, насколько новость реально полезна пользователю с указанными интересами.
Учитывай значимость события, практическую ценность и соответствие интересам.
Не повышай оценку рекламным, повторяющимся и малозначимым публикациям.
Категория должна быть одной из: ai, russian_market, geopolitics, russia_ukraine, startups.
Не добавляй факты, которых нет во входных данных.
"""

NEWS_SUMMARY_PROMPT = """Ты суммируешь только предоставленные реальные статьи.

Результат предназначен для русскоязычной ежедневной сводки.

Для каждого входного элемента верни ровно один результат с тем же index.
Все поля пиши на естественном русском языке. Английские заголовки и описания переводи,
но названия компаний, продуктов, моделей и имена людей сохраняй без искажений.
headline — конкретный заголовок без кликбейта: кто сделал что и, если есть, в каком масштабе.
summary — 2-3 коротких предложения. Укажи участников, действие, сумму, продукт или срок,
если эти данные есть в статье. Не начинай с общих слов и не дублируй заголовок.
why_it_matters — 1-2 предложения о конкретном последствии для технологий, бизнеса,
рынка или геополитических рисков. Не используй пустые формулировки вроде «может повлиять»
без объяснения, на что именно и через какой механизм.
Не добавляй факты и выводы, которых нет в заголовке или описании статьи.
Если входных данных мало, честно изложи только подтвержденное и не заполняй пробелы догадками.
"""

DIGEST_INTRO_PROMPT = """Составь компактный вводный блок «Главное за день» на русском языке.

Используй только переданные заголовки и summaries. Не добавляй новые факты.
Выдели 3-5 наиболее важных событий списком. Каждый пункт — одно конкретное предложение:
кто, что сделал и почему событие заслуживает внимания. Английские заголовки переводи,
сохраняя названия компаний, продуктов и имена. Если событий меньше — перечисли имеющиеся.
"""


class LLMResponseError(RuntimeError):
    pass


class LLMService:
    def __init__(
        self,
        api_key: str,
        task_model: str,
        transcription_model: str,
        news_model: str | None = None,
    ) -> None:
        self.client = AsyncOpenAI(api_key=api_key, timeout=30.0, max_retries=2)
        self.task_model = task_model
        self.transcription_model = transcription_model
        self.news_model = news_model or task_model

    async def close(self) -> None:
        await self.client.close()

    async def extract_task_metadata(
        self,
        message: str,
        current_datetime: datetime,
        timezone: str,
    ) -> ExtractedTask:
        response = await self.client.responses.parse(
            model=self.task_model,
            instructions=TASK_EXTRACTION_PROMPT,
            input=(
                f"Current datetime: {current_datetime.isoformat()}\n"
                f"Timezone: {timezone}\n"
                f"User message:\n{message}"
            ),
            text_format=ExtractedTask,
        )
        extracted = response.output_parsed
        if extracted is None:
            raise LLMResponseError("OpenAI returned no parsed task")

        due_at = extracted.due_at
        if due_at is not None:
            if due_at.tzinfo is None or due_at.utcoffset() is None:
                due_at = due_at.replace(tzinfo=ZoneInfo(timezone))
            due_at = due_at.astimezone(UTC)
            extracted = extracted.model_copy(update={"due_at": due_at})
        return extracted

    async def transcribe_voice(self, audio_path: Path) -> str:
        with audio_path.open("rb") as audio_file:
            transcription = await self.client.audio.transcriptions.create(
                file=audio_file,
                model=self.transcription_model,
                language="ru",
                response_format="json",
            )
        text = transcription.text.strip()
        if not text:
            raise LLMResponseError("OpenAI returned an empty transcription")
        return text

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
        response = await self.client.responses.parse(
            model=self.news_model,
            instructions=NEWS_SCORING_PROMPT,
            input=json.dumps(
                {"interests": interests, "articles": payload},
                ensure_ascii=False,
            ),
            text_format=NewsScoreBatch,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise LLMResponseError("OpenAI returned no parsed news scores")
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
        response = await self.client.responses.parse(
            model=self.news_model,
            instructions=NEWS_SUMMARY_PROMPT,
            input=json.dumps(payload, ensure_ascii=False),
            text_format=NewsSummaryBatch,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise LLMResponseError("OpenAI returned no parsed news summaries")
        return parsed.root

    async def build_digest_intro(self, articles: list[NewsSummary]) -> DigestIntro:
        response = await self.client.responses.parse(
            model=self.news_model,
            instructions=DIGEST_INTRO_PROMPT,
            input=json.dumps(
                [
                    {"headline": article.headline, "summary": article.summary}
                    for article in articles[:5]
                ],
                ensure_ascii=False,
            ),
            text_format=DigestIntro,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise LLMResponseError("OpenAI returned no parsed digest intro")
        return parsed
