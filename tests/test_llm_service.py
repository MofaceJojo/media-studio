import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIStatusError, RateLimitError

from morpheus_video_studio.services.llm_service import LLMService, _create_with_retry


def _make_service() -> LLMService:
    return LLMService({"llm": {"api_key": "test", "base_url": "https://openrouter.ai/api/v1", "model": "m"}})


def _client_with_base_url(url: str):
    return SimpleNamespace(base_url=url)


def test_openrouter_default_keeps_reasoning_enabled_but_excluded() -> None:
    """Mandatory-reasoning models (gpt-oss, r1…) reject reasoning-off requests;
    the default must use lowest effort instead of disabling reasoning."""
    svc = _make_service()
    kwargs: dict = {}
    svc._apply_provider_defaults(_client_with_base_url("https://openrouter.ai/api/v1"), kwargs)

    reasoning = kwargs["extra_body"]["reasoning"]
    assert reasoning["exclude"] is True
    assert reasoning["effort"] != "none"


def test_non_openrouter_providers_get_no_reasoning_injection() -> None:
    svc = _make_service()
    kwargs: dict = {}
    svc._apply_provider_defaults(_client_with_base_url("https://api.deepseek.com/v1"), kwargs)
    assert "extra_body" not in kwargs


def test_user_supplied_reasoning_config_is_not_overridden() -> None:
    svc = _make_service()
    kwargs = {"extra_body": {"reasoning": {"effort": "high"}}}
    svc._apply_provider_defaults(_client_with_base_url("https://openrouter.ai/api/v1"), kwargs)
    assert kwargs["extra_body"]["reasoning"] == {"effort": "high"}


def _rate_limit_error() -> RateLimitError:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(429, request=request, json={"error": {"message": "rate limited"}})
    return RateLimitError("rate limited", response=response, body=None)


def _bad_request_error() -> APIStatusError:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response = httpx.Response(400, request=request, json={"error": {"message": "bad request"}})
    return APIStatusError("bad request", response=response, body=None)


def test_create_with_retry_retries_rate_limits(monkeypatch) -> None:
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(side_effect=[_rate_limit_error(), "ok"])
            )
        )
    )
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    result = asyncio.run(_create_with_retry(client, model="m", messages=[]))

    assert result == "ok"
    assert client.chat.completions.create.await_count == 2


def test_create_with_retry_fails_fast_on_client_errors() -> None:
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(side_effect=_bad_request_error()))
        )
    )

    with pytest.raises(APIStatusError):
        asyncio.run(_create_with_retry(client, model="m", messages=[]))

    assert client.chat.completions.create.await_count == 1
