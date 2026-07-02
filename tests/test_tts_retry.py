# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for OmniVoice TTS transient-failure retry behaviour."""

import asyncio

import httpx
import pytest

from morpheus_video_studio.services.tts_service import TTSService


class _FakeResponse:
    def __init__(self, status_code=200, content=b"fake-audio"):
        self.status_code = status_code
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://127.0.0.1:3900/v1/audio/speech")
            response = httpx.Response(self.status_code, request=request, text="boom")
            raise httpx.HTTPStatusError("error", request=request, response=response)


class _FakeAsyncClient:
    """Substitute for httpx.AsyncClient driven by a scripted list of outcomes."""

    outcomes = []
    post_calls = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, json=None):
        type(self).post_calls += 1
        outcome = type(self).outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def tts(tmp_path):
    service = TTSService(config={"comfyui": {"tts": {}}})
    return service, str(tmp_path / "out.mp3")


@pytest.fixture
def fake_client(monkeypatch):
    _FakeAsyncClient.outcomes = []
    _FakeAsyncClient.post_calls = 0
    monkeypatch.setattr(
        "morpheus_video_studio.services.tts_service.httpx.AsyncClient",
        _FakeAsyncClient,
    )
    # Skip the real backoff waits so the failure paths run instantly
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(
        "morpheus_video_studio.services.tts_service.asyncio.sleep",
        _no_sleep,
    )
    return _FakeAsyncClient


def test_retries_transient_connect_error(tts, fake_client):
    service, output_path = tts
    request = httpx.Request("POST", "http://127.0.0.1:3900/v1/audio/speech")
    fake_client.outcomes = [
        httpx.ConnectError("refused", request=request),
        httpx.ReadTimeout("slow", request=request),
        _FakeResponse(),
    ]

    result = asyncio.run(
        service._call_omnivoice_tts(text="你好", output_path=output_path)
    )

    assert result == output_path
    assert fake_client.post_calls == 3
    with open(output_path, "rb") as f:
        assert f.read() == b"fake-audio"


def test_retries_server_error_then_succeeds(tts, fake_client):
    service, output_path = tts
    fake_client.outcomes = [_FakeResponse(status_code=502), _FakeResponse()]

    result = asyncio.run(
        service._call_omnivoice_tts(text="你好", output_path=output_path)
    )

    assert result == output_path
    assert fake_client.post_calls == 2


def test_client_error_fails_immediately(tts, fake_client):
    service, output_path = tts
    fake_client.outcomes = [_FakeResponse(status_code=422)]

    with pytest.raises(RuntimeError):
        asyncio.run(service._call_omnivoice_tts(text="你好", output_path=output_path))

    assert fake_client.post_calls == 1


def test_gives_up_after_max_attempts(tts, fake_client):
    service, output_path = tts
    request = httpx.Request("POST", "http://127.0.0.1:3900/v1/audio/speech")
    fake_client.outcomes = [
        httpx.ConnectError("refused", request=request),
        httpx.ConnectError("refused", request=request),
        httpx.ConnectError("refused", request=request),
    ]

    with pytest.raises(RuntimeError):
        asyncio.run(service._call_omnivoice_tts(text="你好", output_path=output_path))

    assert fake_client.post_calls == 3
