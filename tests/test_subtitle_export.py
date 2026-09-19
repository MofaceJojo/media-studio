from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from morpheus_video_studio.models.storyboard import (
    Storyboard,
    StoryboardConfig,
    StoryboardFrame,
)
from morpheus_video_studio.pipelines.linear import PipelineContext
from morpheus_video_studio.pipelines.standard import StandardPipeline
from morpheus_video_studio.services.persistence import PersistenceService
from morpheus_video_studio.utils.audio_timing import AudioTiming, detect_audio_timing
from morpheus_video_studio.utils.subtitle_export import (
    SubtitleCue,
    TimelineSegment,
    _format_timestamp,
    _ordered_minimum_cost_pairs,
    build_global_cues,
    export_srt,
    export_srt_cues,
    plan_segment_cues,
)


def _compact(text: str) -> str:
    return "".join(text.split())


@pytest.mark.parametrize(
    ("text", "max_chars"),
    [
        ("你好，世界！这是字幕。", 6),
        ("这是一段没有标点但是需要按长度分割的旁白文字", 5),
        ("AI video，中文混排 works!", 7),
    ],
)
def test_plan_segment_cues_preserves_text_and_limits_phrase_length(
    text: str, max_chars: int
) -> None:
    timing = AudioTiming(duration=8.0, speech_start=0.4, speech_end=7.5, pauses=[])

    cues = plan_segment_cues(text, timing, max_chars=max_chars)

    assert _compact("".join(cue.text for cue in cues)) == _compact(text)
    assert all(len(cue.text) <= max_chars for cue in cues)
    assert [(cue.start, cue.end) for cue in cues] == sorted(
        (cue.start, cue.end) for cue in cues
    )
    assert all(left.end <= right.start for left, right in zip(cues, cues[1:]))


def test_plan_segment_cues_uses_measured_speech_window_and_pause_midpoints() -> None:
    timing = AudioTiming(
        duration=5.0,
        speech_start=0.5,
        speech_end=4.5,
        pauses=[(1.75, 2.25), (3.0, 3.2)],
    )

    cues = plan_segment_cues("第一句，第二句。第三句", timing, max_chars=4)

    assert cues[0].start == 0.5
    assert cues[-1].end == 4.5
    assert cues[0].end == cues[1].start == 2.0
    assert cues[1].end == cues[2].start == 3.1


def test_plan_segment_cues_matches_a_single_pause_to_its_closest_boundary() -> None:
    timing = AudioTiming(6.0, 0.0, 6.0, [(3.5, 3.7)])

    cues = plan_segment_cues("甲，乙，丙。", timing, max_chars=4)

    assert cues[1].end == cues[2].start == 3.6


def test_ordered_pause_matching_uses_bounded_dynamic_programming() -> None:
    targets = [float(index) for index in range(80)]
    midpoints = [float(index * 2) + 0.1 for index in range(40)]
    state_count = [0]

    pairs = _ordered_minimum_cost_pairs(targets, midpoints, state_count=state_count)

    assert pairs == [(index * 2, index) for index in range(40)]
    assert state_count == [(len(targets) + 1) * (len(midpoints) + 1)]


def test_plan_segment_cues_returns_no_cues_for_empty_text_or_no_speech() -> None:
    usable = AudioTiming(duration=1.0, speech_start=0.0, speech_end=1.0, pauses=[])
    silent = AudioTiming(duration=1.0, speech_start=0.0, speech_end=0.0, pauses=[])

    assert plan_segment_cues("", usable) == []
    assert plan_segment_cues("旁白", silent) == []


def test_detect_audio_timing_parses_ffmpeg_silencedetect(monkeypatch: pytest.MonkeyPatch) -> None:
    class Result:
        stderr = (
            "Duration: 00:00:05.00, start: 0.000000\n"
            "silence_start: 0\nsilence_end: 0.500 | silence_duration: 0.500\n"
            "silence_start: 2.000\nsilence_end: 2.300 | silence_duration: 0.300\n"
            "silence_start: 4.500\nsilence_end: 5.000 | silence_duration: 0.500\n"
        )

    monkeypatch.setattr(
        "morpheus_video_studio.utils.audio_timing.subprocess.run",
        lambda *args, **kwargs: Result(),
    )

    timing = detect_audio_timing("voice.mp3")

    assert timing == AudioTiming(5.0, 0.5, 4.5, [(2.0, 2.3)])


def test_build_global_cues_preserves_scene_gaps_and_speech_windows() -> None:
    segments = [
        TimelineSegment(
            "第一句，第二句。",
            AudioTiming(3.0, 0.5, 2.5, [(1.3, 1.5)]),
            timeline_duration=3.5,
        ),
        TimelineSegment(
            "第三句。",
            AudioTiming(2.0, 0.2, 1.4, []),
            timeline_duration=2.0,
        ),
    ]

    cues = build_global_cues(segments, max_chars=4)

    assert cues[0].start == 0.5
    assert cues[-1].end == 4.9
    assert all(cue.end <= 2.5 or cue.start >= 3.7 for cue in cues)
    assert all(left.end <= right.start for left, right in zip(cues, cues[1:]))


def test_export_srt_cues_serializes_supplied_times_exactly(tmp_path: Path) -> None:
    srt_path = tmp_path / "cues.srt"
    cues = [SubtitleCue("开场", 0.125, 1.875), SubtitleCue("收尾", 2.0, 3.005)]

    assert export_srt_cues(cues, str(srt_path)) == str(srt_path)

    assert srt_path.read_text(encoding="utf-8") == (
        "1\n00:00:00,125 --> 00:00:01,875\n开场\n\n"
        "2\n00:00:02,000 --> 00:00:03,005\n收尾\n"
    )


def test_export_srt_uses_zero_leading_silence_compatibility_planning(tmp_path: Path) -> None:
    srt_path = tmp_path / "final.srt"

    export_srt([("第一句，第二句。", 4.0)], str(srt_path))

    content = srt_path.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:04,000" not in content
    assert content.count("-->") == 2
    assert "00:00:00,000" in content
    assert "00:00:04,000" in content


@pytest.mark.asyncio
async def test_persistence_round_trips_audio_duration_and_recovers_legacy_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = PersistenceService(str(tmp_path))
    config = StoryboardConfig(media_width=1080, media_height=1920)
    frame = StoryboardFrame(0, "旁白", "提示", audio_path="voice.mp3", duration=4.0, audio_duration=3.2)
    storyboard = Storyboard("标题", config, [frame])

    await service.save_storyboard("new", storyboard)
    assert (await service.load_storyboard("new")).frames[0].audio_duration == 3.2

    legacy = service._storyboard_to_dict(storyboard)
    legacy["frames"][0].pop("audio_duration")
    monkeypatch.setattr(service, "_probe_audio_duration", lambda path: 2.75)
    recovered = service._dict_to_storyboard(legacy)

    assert recovered.frames[0].audio_duration == 2.75


@pytest.mark.asyncio
async def test_persistence_recovers_zero_audio_duration_from_legacy_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = PersistenceService(str(tmp_path))
    config = StoryboardConfig(media_width=1080, media_height=1920)
    frame = StoryboardFrame(0, "旁白", "提示", audio_path="voice.mp3", duration=4.0)
    legacy = service._storyboard_to_dict(Storyboard("标题", config, [frame]))
    legacy["frames"][0]["audio_duration"] = 0.0
    monkeypatch.setattr(service, "_probe_audio_duration", lambda path: 2.75)

    recovered = service._dict_to_storyboard(legacy)

    assert recovered.frames[0].audio_duration == 2.75


def test_format_timestamp_rounds_milliseconds() -> None:
    assert _format_timestamp(0) == "00:00:00,000"
    assert _format_timestamp(2.934) == "00:00:02,934"
    assert _format_timestamp(3661.5) == "01:01:01,500"


def test_export_srt_lays_segments_back_to_back(tmp_path: Path) -> None:
    srt_path = tmp_path / "final.srt"
    export_srt(
        [
            ("第一句旁白。", 2.93),
            ("第二句旁白，稍微长一点。", 5.64),
            ("第三句收尾。", 4.07),
        ],
        str(srt_path),
    )

    content = srt_path.read_text(encoding="utf-8")
    blocks = [block for block in content.split("\n\n") if block.strip()]
    assert len(blocks) == 4
    assert "00:00:00,000 --> 00:00:02,930" in blocks[0]
    assert "00:00:02,930" in blocks[1]
    assert "00:00:08,570 --> 00:00:12,640" in blocks[3]
    assert "第三句收尾。" in blocks[3]


def test_export_srt_skips_empty_segments_but_keeps_timeline(tmp_path: Path) -> None:
    srt_path = tmp_path / "final.srt"
    export_srt(
        [
            ("开场白。", 3.0),
            ("", 2.0),  # silent gap keeps its slot on the timeline
            ("结束语。", 3.0),
        ],
        str(srt_path),
    )

    content = srt_path.read_text(encoding="utf-8")
    assert "00:00:05,000 --> 00:00:08,000" in content
    assert content.count("-->") == 2


def _post_production_context(
    tmp_path: Path,
    *,
    transition: str = "none",
    transition_audio_delay: float = 0.0,
    subtitle_enabled: bool = True,
    output_path: str | None = None,
) -> PipelineContext:
    config = StoryboardConfig(
        media_width=1080,
        media_height=1920,
        subtitle_enabled=subtitle_enabled,
    )
    frames = [
        StoryboardFrame(
            0,
            "第一句。",
            "画面一",
            audio_path="first.wav",
            video_segment_path="first.mp4",
            duration=5.0,
            audio_duration=3.0,
        ),
        StoryboardFrame(
            1,
            "第二句。",
            "画面二",
            audio_path="second.wav",
            video_segment_path="second.mp4",
            duration=7.0,
            audio_duration=4.0,
        ),
    ]
    params = {
        "transition_mode": transition,
        "transition_audio_delay": transition_audio_delay,
    }
    if output_path is not None:
        params["output_path"] = output_path
    return PipelineContext(
        input_text="",
        params=params,
        final_video_path=str(tmp_path / "internal.mp4"),
        config=config,
        storyboard=Storyboard("标题", config, frames, total_duration=12.0),
    )


def _pipeline() -> StandardPipeline:
    core = SimpleNamespace(llm=None, tts=None, media=None, video=None)
    return StandardPipeline(core)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("transition", "audio_gap", "expected_gap", "expected_second_start"),
    [
        ("none", 0.6, 0.6, 5.0),
        ("fade", 0.6, 0.6, 3.6),
        ("fade", -0.6, 0.0, 3.0),
    ],
)
async def test_post_production_builds_cues_from_actual_concat_audio_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    transition: str,
    audio_gap: float,
    expected_gap: float,
    expected_second_start: float,
) -> None:
    import morpheus_video_studio.pipelines.standard as standard_module

    ctx = _post_production_context(
        tmp_path,
        transition=transition,
        transition_audio_delay=audio_gap,
    )
    Path(ctx.final_video_path).write_bytes(b"video")
    service = MagicMock()
    service.concat_videos.return_value = ctx.final_video_path
    service._should_use_xfade.return_value = transition == "fade"
    service.burn_subtitles.side_effect = lambda video, subtitle_file, output, **style: output
    captured = {}

    def export(cues, path):
        captured["cues"] = cues
        captured["srt_path"] = path
        Path(path).write_text("subtitle", encoding="utf-8")
        return path

    monkeypatch.setattr(standard_module, "VideoService", lambda: service)
    def detector(path):
        duration = 3.0 if path == "first.wav" else 4.0
        return AudioTiming(duration, 0.0, duration, [])

    thread_calls = []

    async def to_thread(function, *args, **kwargs):
        thread_calls.append((function, args, kwargs))
        return function(*args, **kwargs)

    monkeypatch.setattr(standard_module, "detect_audio_timing", detector)
    monkeypatch.setattr(standard_module.asyncio, "to_thread", to_thread)
    monkeypatch.setattr(standard_module, "export_srt_cues", export, raising=False)
    monkeypatch.setattr(standard_module, "inspect_final_video", lambda *args, **kwargs: SimpleNamespace(warnings=[]))

    await _pipeline().post_production(ctx)

    second_cue = next(cue for cue in captured["cues"] if cue.text == "第二句。")
    assert second_cue.start == pytest.approx(expected_second_start)
    assert service.concat_videos.call_args.kwargs["transition_audio_delay"] == expected_gap
    assert [args[0] for function, args, _ in thread_calls if function is detector] == [
        "first.wav",
        "second.wav",
    ]
    burned = service.burn_subtitles.call_args
    assert burned.args[1] == captured["srt_path"]
    assert burned.args[2] == ctx.final_video_path
    assert burned.kwargs["cues"] is captured["cues"]


@pytest.mark.asyncio
async def test_subtitle_disabled_skips_export_and_burn_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import morpheus_video_studio.pipelines.standard as standard_module

    ctx = _post_production_context(tmp_path, subtitle_enabled=False)
    Path(ctx.final_video_path).write_bytes(b"video")
    service = MagicMock()
    service.concat_videos.return_value = ctx.final_video_path
    service._should_use_xfade.return_value = False
    export = MagicMock()
    monkeypatch.setattr(standard_module, "VideoService", lambda: service)
    monkeypatch.setattr(standard_module, "export_srt_cues", export, raising=False)
    monkeypatch.setattr(standard_module, "inspect_final_video", lambda *args, **kwargs: SimpleNamespace(warnings=[]))

    await _pipeline().post_production(ctx)

    export.assert_not_called()
    service.burn_subtitles.assert_not_called()
    assert not Path(ctx.final_video_path).with_suffix(".srt").exists()


@pytest.mark.asyncio
async def test_burn_in_happens_before_user_output_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import morpheus_video_studio.pipelines.standard as standard_module

    user_output = tmp_path / "delivery" / "final.mp4"
    ctx = _post_production_context(tmp_path, output_path=str(user_output))
    internal = Path(ctx.final_video_path)
    internal.write_bytes(b"raw")
    service = MagicMock()
    service.concat_videos.return_value = str(internal)
    service._should_use_xfade.return_value = False

    def burn(video, subtitle_file, output, **style):
        Path(output).write_bytes(b"burned")
        return output

    service.burn_subtitles.side_effect = burn
    monkeypatch.setattr(standard_module, "VideoService", lambda: service)
    monkeypatch.setattr(
        standard_module,
        "detect_audio_timing",
        lambda path: AudioTiming(1.0, 0.0, 1.0, []),
        raising=False,
    )
    monkeypatch.setattr(
        standard_module,
        "export_srt_cues",
        lambda cues, path: Path(path).write_text("subtitle", encoding="utf-8") or path,
        raising=False,
    )
    monkeypatch.setattr(standard_module, "inspect_final_video", lambda *args, **kwargs: SimpleNamespace(warnings=[]))

    await _pipeline().post_production(ctx)

    assert internal.read_bytes() == b"burned"
    assert user_output.read_bytes() == b"burned"
    assert ctx.final_video_path == str(user_output)
