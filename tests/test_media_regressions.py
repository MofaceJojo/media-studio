import asyncio
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.modules.setdefault("comfykit", types.SimpleNamespace(ComfyKit=object))

from morpheus_video_studio.services.tts_service import TTSService
from morpheus_video_studio.services.video import VideoService


def test_concat_videos_single_clip_with_bgm_still_runs_bgm_pipeline(monkeypatch, tmp_path: Path) -> None:
    service = VideoService()
    input_video = tmp_path / "input.mp4"
    output_video = tmp_path / "output.mp4"
    bgm_path = tmp_path / "bgm.mp3"
    input_video.write_bytes(b"fake-video")
    bgm_path.write_bytes(b"fake-bgm")

    monkeypatch.setattr(service, "_ensure_ffmpeg", lambda: None)

    calls: dict[str, str] = {}

    def fake_add_bgm(*, video: str, bgm_path: str, output: str, volume: float, mode: str) -> str:
        calls["video"] = video
        calls["bgm_path"] = bgm_path
        calls["output"] = output
        Path(output).write_bytes(b"with-bgm")
        return output

    monkeypatch.setattr(service, "_add_bgm_to_video", fake_add_bgm)

    result = service.concat_videos(
        [str(input_video)],
        str(output_video),
        bgm_path=str(bgm_path),
    )

    assert result == str(output_video)
    assert calls == {
        "video": str(input_video),
        "bgm_path": str(bgm_path),
        "output": str(output_video),
    }
    assert output_video.read_bytes() == b"with-bgm"


def test_omnivoice_tts_forwards_selected_model_and_voice(monkeypatch, tmp_path: Path) -> None:
    config = {
        "comfyui": {
            "tts": {
                "inference_mode": "omnivoice",
                "omnivoice": {
                    "base_url": "http://127.0.0.1:3900",
                    "model": "omnivoice",
                    "voice": "default",
                    "speed": 1.0,
                },
            }
        }
    }
    service = TTSService(config)
    output_path = tmp_path / "speech.mp3"

    monkeypatch.setattr(
        "morpheus_video_studio.services.tts_service.fetch_omnivoice_model_status",
        lambda *args, **kwargs: {"status": "ready", "loaded": True, "loading": False},
    )
    monkeypatch.setattr(
        "morpheus_video_studio.services.tts_service.generate_omnivoice_audio",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("shared OmniVoice TTS should not use the legacy /generate endpoint")
        ),
        raising=False,
    )

    captured: dict[str, object] = {}

    def fake_openai_speech(
        base_url: str,
        *,
        text: str,
        model: str,
        voice: str,
        response_format: str,
        speed: float,
        language: str | None = None,
        instruct: str | None = None,
        duration: float | None = None,
        seed: int | None = None,
        timeout: float = 0.0,
    ) -> dict[str, object]:
        captured.update(
            {
                "base_url": base_url,
                "text": text,
                "model": model,
                "voice": voice,
                "response_format": response_format,
                "speed": speed,
                "language": language,
                "instruct": instruct,
                "duration": duration,
                "seed": seed,
                "timeout": timeout,
            }
        )
        return {"audio_bytes": b"audio-bytes", "media_type": "audio/mpeg"}

    monkeypatch.setattr(
        "morpheus_video_studio.services.tts_service.generate_omnivoice_openai_speech",
        fake_openai_speech,
        raising=False,
    )

    result = asyncio.run(
        service._call_omnivoice_tts(
            text="测试 OmniVoice",
            voice="demo0001",
            model="voxcpm2",
            speed=1.3,
            output_path=str(output_path),
            instruct="女，青年",
        )
    )

    assert result == str(output_path)
    assert output_path.read_bytes() == b"audio-bytes"
    assert captured["base_url"] == "http://127.0.0.1:3900"
    assert captured["text"] == "测试 OmniVoice"
    assert captured["model"] == "voxcpm2"
    assert captured["voice"] == "demo0001"
    assert captured["response_format"] == "mp3"
    assert captured["speed"] == 1.3
    assert captured["instruct"] == "女，青年"
