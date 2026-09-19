from pathlib import Path

import ffmpeg

from morpheus_video_studio.models.storyboard import StoryboardConfig
from morpheus_video_studio.services.video import VideoService
from web.components.video_generation_config import _estimate_scene_trailing_silence


def _make_segment(path: Path, color: str, frequency: int, duration: float = 1.0) -> None:
    video = ffmpeg.input(
        f"color=c={color}:s=320x240:r=24:d={duration}",
        f="lavfi",
    ).video
    audio = ffmpeg.input(
        f"sine=frequency={frequency}:sample_rate=48000:duration={duration}",
        f="lavfi",
    ).audio
    (
        ffmpeg.output(
            video,
            audio,
            str(path),
            vcodec="libx264",
            acodec="aac",
            pix_fmt="yuv420p",
            shortest=None,
        )
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )


def test_storyboard_defaults_follow_audio_length_without_extra_padding() -> None:
    config = StoryboardConfig(media_width=1920, media_height=1080)

    assert config.min_segment_duration == 0.0
    assert config.scene_trailing_silence == 0.0


def test_quick_create_trailing_silence_default_is_zero() -> None:
    assert _estimate_scene_trailing_silence(0.5) == 0.0


def test_concat_videos_xfade_does_not_insert_default_audio_gap(tmp_path: Path) -> None:
    service = VideoService()
    videos = []
    for index, color in enumerate(["red", "blue", "green"]):
        path = tmp_path / f"segment_{index + 1}.mp4"
        _make_segment(path, color, 440 + index * 30, duration=1.0)
        videos.append(str(path))

    output = tmp_path / "xfade.mp4"
    service.concat_videos(
        videos,
        str(output),
        transition="fade",
        transition_duration=0.25,
    )

    duration = float(ffmpeg.probe(str(output))["format"]["duration"])

    assert 2.9 <= duration <= 3.15
