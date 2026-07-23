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


def _http_status_error(status_code):
    request = httpx.Request("POST", "http://127.0.0.1:3900/v1/audio/speech")
    response = httpx.Response(status_code, request=request, text="boom")
    return httpx.HTTPStatusError("error", request=request, response=response)


class _FakeSpeechBackend:
    """Substitute for generate_omnivoice_openai_speech driven by scripted outcomes."""

    outcomes = []
    calls = 0

    @classmethod
    def generate(cls, base_url, **kwargs):
        cls.calls += 1
        outcome = cls.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def tts(tmp_path):
    service = TTSService(config={"comfyui": {"tts": {}}})
    return service, str(tmp_path / "out.mp3")


@pytest.fixture
def fake_backend(monkeypatch):
    _FakeSpeechBackend.outcomes = []
    _FakeSpeechBackend.calls = 0
    monkeypatch.setattr(
        "morpheus_video_studio.services.tts_service.generate_omnivoice_openai_speech",
        _FakeSpeechBackend.generate,
    )
    # Keep the pre/post model-status probes off the network
    monkeypatch.setattr(
        "morpheus_video_studio.services.tts_service.fetch_omnivoice_model_status",
        lambda base_url, timeout=3.0: {"status": "ready"},
    )
    # Skip the real backoff waits so the failure paths run instantly
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(
        "morpheus_video_studio.services.tts_service.asyncio.sleep",
        _no_sleep,
    )
    return _FakeSpeechBackend


def test_retries_transient_connect_error(tts, fake_backend):
    service, output_path = tts
    request = httpx.Request("POST", "http://127.0.0.1:3900/v1/audio/speech")
    fake_backend.outcomes = [
        httpx.ConnectError("refused", request=request),
        httpx.ReadTimeout("slow", request=request),
        {"audio_bytes": b"fake-audio", "media_type": "audio/mpeg"},
    ]

    result = asyncio.run(
        service._call_omnivoice_tts(text="你好", output_path=output_path)
    )

    assert result == output_path
    assert fake_backend.calls == 3
    with open(output_path, "rb") as f:
        assert f.read() == b"fake-audio"


def test_retries_server_error_then_succeeds(tts, fake_backend):
    service, output_path = tts
    fake_backend.outcomes = [
        _http_status_error(502),
        {"audio_bytes": b"fake-audio", "media_type": "audio/mpeg"},
    ]

    result = asyncio.run(
        service._call_omnivoice_tts(text="你好", output_path=output_path)
    )

    assert result == output_path
    assert fake_backend.calls == 2


def test_client_error_fails_immediately(tts, fake_backend):
    service, output_path = tts
    fake_backend.outcomes = [_http_status_error(422)]

    with pytest.raises(RuntimeError):
        asyncio.run(service._call_omnivoice_tts(text="你好", output_path=output_path))

    assert fake_backend.calls == 1


def test_gives_up_after_max_attempts(tts, fake_backend):
    service, output_path = tts
    request = httpx.Request("POST", "http://127.0.0.1:3900/v1/audio/speech")
    fake_backend.outcomes = [
        httpx.ConnectError("refused", request=request),
        httpx.ConnectError("refused", request=request),
        httpx.ConnectError("refused", request=request),
    ]

    with pytest.raises(RuntimeError):
        asyncio.run(service._call_omnivoice_tts(text="你好", output_path=output_path))

    assert fake_backend.calls == 3
