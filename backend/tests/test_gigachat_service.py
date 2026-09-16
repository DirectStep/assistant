import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.services.gigachat_service import GigaChatService


async def test_gigachat_extracts_task_and_reuses_access_token() -> None:
    oauth_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal oauth_calls
        if request.url.path == "/api/v2/oauth":
            oauth_calls += 1
            assert request.headers["Authorization"] == "Basic auth-key"
            return httpx.Response(
                200,
                json={"access_token": "access-token", "expires_at": time.time() + 1800},
            )
        assert request.headers["Authorization"] == "Bearer access-token"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "title": "В пятницу отправить отчёт",
                                    "due_at": "2026-09-18T18:00:00",
                                    "important": False,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    service = GigaChatService(
        "auth-key",
        "GIGACHAT_API_PERS",
        "GigaChat-2",
        transport=httpx.MockTransport(handler),
    )
    try:
        first = await service.extract_task_metadata(
            "В пятницу отправить отчёт",
            datetime(2026, 9, 16, 12, 0, tzinfo=UTC),
            "Europe/Moscow",
        )
        await service.extract_task_metadata(
            "В пятницу отправить отчёт",
            datetime(2026, 9, 16, 12, 0, tzinfo=UTC),
            "Europe/Moscow",
        )
    finally:
        await service.close()

    assert first.due_at == datetime(2026, 9, 18, 15, 0, tzinfo=UTC)
    assert oauth_calls == 1


async def test_gigachat_transcribes_and_deletes_voice_file(tmp_path: Path) -> None:
    called_paths: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        called_paths.append(request.url.path)
        if request.url.path == "/api/v2/oauth":
            return httpx.Response(
                200,
                json={"access_token": "access-token", "expires_at": time.time() + 1800},
            )
        if request.url.path == "/v1/files":
            return httpx.Response(200, json={"id": "voice-file"})
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "  Отправить таблицу  "}}]},
            )
        if request.url.path == "/v1/files/voice-file/delete":
            return httpx.Response(200, json={"deleted": True})
        return httpx.Response(404)

    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"fake ogg")
    service = GigaChatService(
        "auth-key",
        "GIGACHAT_API_PERS",
        "GigaChat-2",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await service.transcribe_voice(audio_path)
    finally:
        await service.close()

    assert result == "Отправить таблицу"
    assert "/v1/files" in called_paths
    assert called_paths[-1] == "/v1/files/voice-file/delete"
