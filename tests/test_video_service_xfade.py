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
