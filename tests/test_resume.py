"""Resume core mechanism: a frame whose segment already exists is reused,
not regenerated. (Full pipeline resume verified end-to-end under the venv;
this locks the reusable guard that makes it work.)"""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from morpheus_video_studio.services.frame_processor import FrameProcessor
from morpheus_video_studio.models.storyboard import StoryboardFrame, StoryboardConfig


def _frame(idx=0):
    return StoryboardFrame(index=idx, narration="测试", image_prompt="x")


def test_existing_segment_is_reused_and_steps_skipped(tmp_path, monkeypatch):
    from morpheus_video_studio.utils import os_util
    seg = tmp_path / "00_segment.mp4"
    seg.write_bytes(b"fake")
    monkeypatch.setattr(os_util, "get_task_frame_path", lambda *a, **k: str(seg))

    fp = FrameProcessor(SimpleNamespace())
    fp._get_video_duration = AsyncMock(return_value=2.5)
    # If reuse works, none of the 4 steps run:
    fp._step_generate_audio = AsyncMock(side_effect=AssertionError("should skip"))
    fp._step_create_video_segment = AsyncMock(side_effect=AssertionError("should skip"))

    frame = _frame()
    out = asyncio.run(fp(frame=frame, storyboard=None,
                        config=StoryboardConfig(task_id="t1", media_width=1080, media_height=1920), total_frames=1))
    assert out.video_segment_path == str(seg)
    assert out.duration == 2.5


def test_missing_segment_runs_generation(tmp_path, monkeypatch):
    from morpheus_video_studio.utils import os_util
    monkeypatch.setattr(os_util, "get_task_frame_path",
                        lambda *a, **k: str(tmp_path / "nope_segment.mp4"))
    fp = FrameProcessor(SimpleNamespace())
    ran = {"audio": False}

    async def fake_audio(frame, config):
        ran["audio"] = True
        raise RuntimeError("stop after audio")  # halt early; we only assert it ran
    fp._step_generate_audio = fake_audio

    try:
        asyncio.run(fp(frame=_frame(), storyboard=None,
                       config=StoryboardConfig(task_id="t2", media_width=1080, media_height=1920), total_frames=1))
    except RuntimeError:
        pass
    assert ran["audio"] is True  # no existing segment → generation proceeds
