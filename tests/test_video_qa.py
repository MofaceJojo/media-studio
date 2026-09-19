from pathlib import Path

import ffmpeg
import pytest

from morpheus_video_studio.utils.video_qa import inspect_final_video


def _make_video(
    path: Path,
    duration: float,
    moving: bool = True,
    silent: bool = False,
) -> None:
    """Render a small test video: moving/static picture + tone/silent audio."""
    video_source = "testsrc=size=320x240:rate=24" if moving else "color=c=steelblue:size=320x240:rate=24"
    audio_source = "anullsrc=r=44100:cl=mono" if silent else "sine=frequency=440:sample_rate=44100"
    video_in = ffmpeg.input(video_source, f="lavfi", t=duration)
    audio_in = ffmpeg.input(audio_source, f="lavfi", t=duration)
    (
        ffmpeg.output(
            video_in.video,
            audio_in.audio,
            str(path),
            vcodec="libx264",
            acodec="aac",
            pix_fmt="yuv420p",
        )
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )


def test_qa_passes_healthy_video(tmp_path: Path) -> None:
    video = tmp_path / "good.mp4"
    _make_video(video, duration=6.0, moving=True, silent=False)

    report = inspect_final_video(str(video), expected_duration_seconds=6.0)

    assert report.ok
    assert report.warnings == []
    assert 5.5 <= report.duration_seconds <= 6.5


def test_qa_flags_duration_drift(tmp_path: Path) -> None:
    video = tmp_path / "short.mp4"
    _make_video(video, duration=5.0, moving=True, silent=False)

    report = inspect_final_video(str(video), expected_duration_seconds=12.0)

    assert not report.ok
    assert any("偏差" in warning for warning in report.warnings)


def test_qa_flags_frozen_picture(tmp_path: Path) -> None:
    video = tmp_path / "frozen.mp4"
    _make_video(video, duration=12.0, moving=False, silent=False)

    report = inspect_final_video(
        str(video),
        expected_duration_seconds=12.0,
        freeze_threshold_seconds=8.0,
    )

    assert not report.ok
    assert any("静止" in warning for warning in report.warnings)


def test_qa_flags_silent_narration(tmp_path: Path) -> None:
    video = tmp_path / "silent.mp4"
    _make_video(video, duration=12.0, moving=True, silent=True)

    report = inspect_final_video(
        str(video),
        expected_duration_seconds=12.0,
        silence_threshold_seconds=3.0,
    )

    assert not report.ok
    assert any("静音" in warning for warning in report.warnings)


def test_qa_flags_unreadable_file(tmp_path: Path) -> None:
    fake = tmp_path / "broken.mp4"
    fake.write_bytes(b"not a real video")

    report = inspect_final_video(str(fake))

    assert not report.ok
    assert report.warnings
