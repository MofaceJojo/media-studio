from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from morpheus_video_studio.models.storyboard import (
    Storyboard,
    StoryboardConfig,
    StoryboardFrame,
)
from morpheus_video_studio.services.frame_processor import FrameProcessor


def _config(**overrides) -> StoryboardConfig:
    values = {"media_width": 1080, "media_height": 1920, "task_id": "subtitles"}
    values.update(overrides)
    return StoryboardConfig(**values)


@pytest.mark.asyncio
async def test_generated_tts_preserves_raw_audio_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    core = SimpleNamespace(tts=AsyncMock(return_value="voice.mp3"))
    processor = FrameProcessor(core)
    processor._get_audio_duration = AsyncMock(return_value=3.25)
    frame = StoryboardFrame(0, "旁白", "画面")
    monkeypatch.setattr(
        "morpheus_video_studio.utils.os_util.get_task_frame_path",
        lambda *args: "generated.mp3",
    )

    await processor._step_generate_audio(frame, _config())

    assert frame.audio_path == "voice.mp3"
    assert frame.audio_duration == 3.25
    assert frame.duration == 3.25


@pytest.mark.asyncio
async def test_reused_segment_reprobes_its_narration_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    segment = tmp_path / "segment.mp4"
    segment.write_bytes(b"existing")
    monkeypatch.setattr(
        "morpheus_video_studio.utils.os_util.get_task_frame_path",
        lambda *args: str(segment),
    )
    processor = FrameProcessor(SimpleNamespace())
    processor._get_video_duration = AsyncMock(return_value=5.0)
    processor._get_audio_duration = AsyncMock(return_value=3.5)
    frame = StoryboardFrame(0, "旁白", "画面", audio_path="voice.mp3")

    result = await processor(frame, None, _config())

    assert result.duration == 5.0
    assert result.audio_duration == 3.5
    processor._get_audio_duration.assert_awaited_once_with("voice.mp3")


@pytest.mark.asyncio
@pytest.mark.parametrize("subtitle_enabled", [True, False])
async def test_html_composition_never_renders_static_narration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    subtitle_enabled: bool,
) -> None:
    received = {}

    class Generator:
        def __init__(self, template_path: str) -> None:
            received["template_path"] = template_path

        async def generate_frame(self, **kwargs) -> str:
            received.update(kwargs)
            return kwargs["output_path"]

    monkeypatch.setattr(
        "morpheus_video_studio.services.frame_html.HTMLFrameGenerator", Generator
    )
    monkeypatch.setattr(
        "morpheus_video_studio.utils.template_util.resolve_template_path",
        lambda path: "template.html",
    )
    frame = StoryboardFrame(
        0,
        "这一整段旁白只能出现在动态字幕中",
        "画面",
        media_type="image",
        image_path="image.png",
    )
    config = _config(subtitle_enabled=subtitle_enabled)
    storyboard = Storyboard("保留标题", config, [frame])

    await FrameProcessor(SimpleNamespace())._compose_frame_html(
        frame, storyboard, config, str(tmp_path / "frame.png")
    )

    assert received["title"] == "保留标题"
    assert received["text"] == ""
