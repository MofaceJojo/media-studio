import asyncio
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("comfykit")
from morpheus_video_studio.services.tts_service import TTSService


def _svc() -> TTSService:
    return TTSService({"comfyui": {"tts": {"local": {"voice": "zh-CN-YunjianNeural", "speed": 1.0},
                                            "omnivoice": {"base_url": "http://127.0.0.1:3900"}}}})


def test_omnivoice_failure_falls_back_to_edge(tmp_path, monkeypatch):
    svc = _svc()
    # OmniVoice raises (pseudo-ready hang等价), local succeeds
    monkeypatch.setattr(svc, "_call_omnivoice_tts",
                        AsyncMock(side_effect=RuntimeError("OmniVoice 假死")))
    local = AsyncMock(return_value=str(tmp_path / "out.mp3"))
    monkeypatch.setattr(svc, "_call_local_tts", local)

    out = asyncio.run(svc(text="测试降级", inference_mode="omnivoice",
                          output_path=str(tmp_path / "out.mp3")))
    assert out == str(tmp_path / "out.mp3")
    local.assert_awaited_once()
    # 降级时不传 omnivoice 的 voice(对 Edge 无意义)
    assert local.await_args.kwargs["voice"] is None


def test_omnivoice_success_does_not_fall_back(tmp_path, monkeypatch):
    svc = _svc()
    omni = AsyncMock(return_value=str(tmp_path / "o.mp3"))
    local = AsyncMock()
    monkeypatch.setattr(svc, "_call_omnivoice_tts", omni)
    monkeypatch.setattr(svc, "_call_local_tts", local)
    asyncio.run(svc(text="正常", inference_mode="omnivoice", output_path=str(tmp_path / "o.mp3")))
    local.assert_not_awaited()
