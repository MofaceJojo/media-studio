from pathlib import Path

import ffmpeg
from PIL import Image

from morpheus_video_studio.services.video import VideoService
from morpheus_video_studio.utils.content_generators import (
    build_shot_prompt_variants,
    plan_visual_shots,
)


def _make_audio(path: Path, duration: float = 6.0, frequency: int = 440) -> None:
    audio = ffmpeg.input(
        f"sine=frequency={frequency}:sample_rate=48000:duration={duration}",
        f="lavfi",
    ).audio
    (
        ffmpeg.output(audio, str(path), acodec="aac", audio_bitrate="192k")
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )


def _make_image(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (720, 1280), color).save(path)


def test_plan_visual_shots_prefers_multi_shot_segments_for_longer_voiceover() -> None:
    plan = plan_visual_shots(10.8, min_shot_seconds=2.4, max_shot_seconds=4.2, max_shots=3)

    assert plan["shot_count"] == 3
    assert len(plan["shot_durations"]) == 3
    assert round(sum(plan["shot_durations"]), 3) == 10.8
    assert all(3.0 <= duration <= 4.0 for duration in plan["shot_durations"])


def test_plan_visual_shots_breaks_shorter_voiceover_into_two_shots_when_possible() -> None:
    plan = plan_visual_shots(4.2, min_shot_seconds=2.0, max_shot_seconds=3.2, max_shots=4)

    assert plan["shot_count"] == 2
    assert len(plan["shot_durations"]) == 2
    assert round(sum(plan["shot_durations"]), 3) == 4.2


def test_build_shot_prompt_variants_creates_distinct_views() -> None:
    prompts = build_shot_prompt_variants(
        "Song dynasty heroes gather inside a smoky tavern, cinematic realism",
        shot_count=4,
    )

    assert len(prompts) == 4
    assert len(set(prompts)) == 4
    assert prompts[0].startswith("Song dynasty heroes gather")
    assert any("close-up" in prompt.lower() for prompt in prompts[1:])


def test_create_video_from_images_builds_single_segment_with_audio(tmp_path: Path) -> None:
    service = VideoService()
    images = [
        tmp_path / "shot_1.png",
        tmp_path / "shot_2.png",
        tmp_path / "shot_3.png",
    ]
    for image_path, color in zip(images, [(200, 40, 40), (40, 120, 220), (40, 180, 120)]):
        _make_image(image_path, color)

    audio_path = tmp_path / "voice.m4a"
    _make_audio(audio_path, duration=6.0)

    output = tmp_path / "segment.mp4"
    result = service.create_video_from_images(
        images=[str(path) for path in images],
        audio=str(audio_path),
        output=str(output),
        fps=24,
        motion_mode="sequence",
        motion_choices=["gentle", "float", "cinematic"],
        min_duration=6.0,
        trailing_silence=0.3,
    )

    probe = ffmpeg.probe(str(output))
    duration = float(probe["format"]["duration"])

    assert result == str(output)
    assert output.exists()
    assert output.stat().st_size > 0
    assert service.has_audio_stream(str(output))
    assert 6.2 <= duration <= 6.5
