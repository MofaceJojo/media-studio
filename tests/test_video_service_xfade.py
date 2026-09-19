from pathlib import Path

import ffmpeg

from morpheus_video_studio.services.video import VideoService


def _make_segment(path: Path, color: str, frequency: int, duration: float = 1.2) -> None:
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


def test_concat_videos_supports_xfade_with_audio_delay_across_many_segments(tmp_path: Path) -> None:
    service = VideoService()
    colors = ["red", "blue", "green", "yellow", "purple"]
    videos = []

    for index, color in enumerate(colors):
        path = tmp_path / f"segment_{index + 1}.mp4"
        _make_segment(path, color, 440 + (index * 40))
        videos.append(str(path))

    output = tmp_path / "final.mp4"
    result = service.concat_videos(
        videos,
        str(output),
        transition="random",
        transition_choices=["fade", "dissolve", "wipeleft"],
        transition_duration=0.3,
        transition_audio_delay=0.2,
    )

    assert result == str(output)
    assert output.exists()
    assert output.stat().st_size > 0
    assert service.has_audio_stream(str(output))


def _frame_brightness(video: str, timestamp: float, tmp_path: Path) -> float:
    """Mean luma (0-255) of one extracted frame."""
    import subprocess

    import numpy as np
    from PIL import Image

    frame = tmp_path / "probe.png"
    subprocess.run(
        ["ffmpeg", "-v", "quiet", "-ss", str(timestamp), "-i", video,
         "-frames:v", "1", str(frame), "-y"],
        check=True,
    )
    return float(np.asarray(Image.open(frame).convert("L")).mean())


def test_xfade_concat_keeps_last_image_visible_through_tail(tmp_path: Path) -> None:
    """Regression: the last narration must not play over a black screen.

    A per-segment fade-to-black used to bake a black frame into every clip's
    tail; the xfade concat cloned it to pad to narration length, blanking the
    final seconds. Segments are now clean, so the tail stays bright.
    """
    service = VideoService()
    videos = []
    for index, color in enumerate(["white", "white", "white", "white"]):
        path = tmp_path / f"seg_{index + 1}.mp4"
        _make_segment(path, color, 440 + index * 40, duration=1.5)
        videos.append(str(path))

    output = tmp_path / "final.mp4"
    service.concat_videos(
        videos, str(output),
        transition="random",
        transition_choices=["fade", "dissolve", "wipeleft"],
        transition_duration=0.4,
    )

    duration = float(
        ffmpeg.probe(str(output))["format"]["duration"]
    )
    # Sample the final second — must still show the (white) image, not black.
    tail = _frame_brightness(str(output), duration - 0.4, tmp_path)
    assert tail > 100, f"tail frame is too dark ({tail}); last image was blanked"
