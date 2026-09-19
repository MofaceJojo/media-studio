from pathlib import Path
from unittest.mock import MagicMock

import ffmpeg
import numpy as np
import pytest
from PIL import Image

from morpheus_video_studio.services.video import VideoService
from morpheus_video_studio.services.video.subtitles import (
    _ass_color,
    _burn_command,
    _subtitle_style,
)
from morpheus_video_studio.utils.subtitle_export import SubtitleCue


def _make_video(path: Path, duration: float = 1.2) -> None:
    video = ffmpeg.input(
        f"color=c=navy:s=320x240:r=24:d={duration}", f="lavfi"
    ).video
    audio = ffmpeg.input(
        f"sine=frequency=440:sample_rate=48000:duration={duration}", f="lavfi"
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


@pytest.mark.parametrize(
    ("position", "alignment"),
    [("bottom", 2), ("center", 5), ("top", 8)],
)
def test_subtitle_style_maps_named_positions_to_ass_alignment(
    position: str, alignment: int
) -> None:
    style = _subtitle_style(
        font="Noto Sans",
        position=position,
        color="#12ABEF",
        size=42,
        stroke_color="#102030",
        stroke_width=1.5,
    )

    assert f"Alignment={alignment}" in style
    assert "FontName=Noto Sans" in style
    assert "FontSize=42" in style
    assert "Outline=1.5" in style


def test_ass_color_converts_css_rgb_to_ass_bgr() -> None:
    assert _ass_color("#12ABEF") == "&H00EFAB12"
    assert _ass_color("#102030") == "&H00302010"


def test_burn_command_safely_escapes_subtitle_path() -> None:
    command = _burn_command(
        "input.mp4",
        "/tmp/caption:it's here.srt",
        "output.mp4",
        "Alignment=2",
        has_audio=True,
    )

    filter_graph = command[command.index("-filter_complex") + 1]
    assert "caption\\\\:it\\\\\\'s here.srt" in filter_graph
    assert command.count("/tmp/caption:it's here.srt") == 0
    assert command.count("output.mp4") == 1


def test_fallback_uses_constant_ffmpeg_inputs_for_501_cues(tmp_path: Path) -> None:
    import morpheus_video_studio.services.video.subtitles as subtitle_module

    overlays = [
        (str(tmp_path / f"cue_{index:04d}.png"), index / 10, (index + 1) / 10)
        for index in range(501)
    ]
    manifest = tmp_path / "timeline.ffconcat"
    blank = tmp_path / "blank.png"
    subtitle_module._write_overlay_manifest(
        overlays,
        total_duration=51.0,
        manifest_path=manifest,
        blank_path=blank,
    )
    commands = [
        subtitle_module._overlay_video_command(str(manifest), "overlay.mov"),
        subtitle_module._single_overlay_command(
            "input.mp4", "overlay.mov", "output.mp4", has_audio=True
        ),
    ]

    assert len(overlays) == 501
    assert max(command.count("-i") for command in commands) <= 2
    composite_graph = commands[1][commands[1].index("-filter_complex") + 1]
    assert composite_graph.count("overlay=") == 1
    assert "eof_action=pass" in composite_graph
    assert "shortest=1" not in composite_graph


def test_overlay_manifest_clamps_cues_to_video_duration(tmp_path: Path) -> None:
    import morpheus_video_studio.services.video.subtitles as subtitle_module

    manifest = tmp_path / "timeline.ffconcat"
    subtitle_module._write_overlay_manifest(
        [("late.png", 10.0, 11.0)],
        total_duration=1.0,
        manifest_path=manifest,
        blank_path=tmp_path / "blank.png",
    )

    durations = [
        float(line.split()[1])
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.startswith("duration ")
    ]
    assert sum(durations) == pytest.approx(1.0)


def test_pillow_render_wraps_full_width_text_inside_horizontal_margins(
    tmp_path: Path,
) -> None:
    import morpheus_video_studio.services.video.subtitles as subtitle_module

    width, height = 320, 240
    output = tmp_path / "wrapped.png"
    subtitle_module._render_cue_image(
        SubtitleCue("超长全角字幕测试" * 10, 0.0, 1.0),
        output,
        width=width,
        height=height,
        font="PingFang SC",
        position="center",
        color="#FFFFFF",
        size=52,
        stroke_color="#000000",
        stroke_width=2.0,
    )

    alpha = np.asarray(Image.open(output).convert("RGBA"))[:, :, 3]
    y_pixels, x_pixels = np.nonzero(alpha)
    horizontal_margin = max(int(width * 0.05), 8)
    assert x_pixels.min() >= horizontal_margin
    assert x_pixels.max() < width - horizontal_margin
    assert y_pixels.max() - y_pixels.min() > 52


def test_pillow_render_truncates_extreme_text_inside_all_safe_margins(
    tmp_path: Path,
) -> None:
    import morpheus_video_studio.services.video.subtitles as subtitle_module

    width, height = 320, 240
    output = tmp_path / "extreme.png"
    subtitle_module._render_cue_image(
        SubtitleCue("无限超长字幕" * 1000, 0.0, 1.0),
        output,
        width=width,
        height=height,
        font="PingFang SC",
        position="center",
        color="#FFFFFF",
        size=52,
        stroke_color="#000000",
        stroke_width=2.0,
    )

    alpha = np.asarray(Image.open(output).convert("RGBA"))[:, :, 3]
    y_pixels, x_pixels = np.nonzero(alpha)
    horizontal_margin = max(int(width * 0.05), 8)
    vertical_margin = max(int(height * 0.08), 8)
    assert x_pixels.min() >= horizontal_margin
    assert x_pixels.max() < width - horizontal_margin
    assert y_pixels.min() >= vertical_margin
    assert y_pixels.max() < height - vertical_margin


def test_pillow_fit_preserves_normal_18_character_cue() -> None:
    import morpheus_video_studio.services.video.subtitles as subtitle_module

    text = "这是十八个字符的普通字幕需要完整保留"
    canvas = Image.new("RGBA", (320, 240), (0, 0, 0, 0))
    fitted, _, _, _ = subtitle_module._fit_cue_text(
        subtitle_module.ImageDraw.Draw(canvas),
        text,
        "PingFang SC",
        28,
        288,
        120,
        2,
    )

    assert fitted.replace("\n", "") == text
    assert "…" not in fitted


@pytest.mark.parametrize(
    "invalid_duration",
    [pytest.param(0.0, id="zero"), pytest.param(float("nan"), id="nan"), pytest.param(None, id="probe-error")],
)
def test_fallback_fails_closed_when_video_duration_is_invalid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid_duration: float | None,
) -> None:
    import morpheus_video_studio.services.video.subtitles as subtitle_module

    source = tmp_path / "source.mp4"
    subtitle = tmp_path / "captions.srt"
    output = tmp_path / "output.mp4"
    source.write_bytes(b"source")
    subtitle.write_text("", encoding="utf-8")
    output.write_bytes(b"original")
    service = VideoService()
    runner = MagicMock()
    replace = MagicMock()
    monkeypatch.setattr(subtitle_module, "_ffmpeg_has_subtitles_filter", lambda: False)
    monkeypatch.setattr(subtitle_module.os, "replace", replace)
    monkeypatch.setattr(service, "_ensure_ffmpeg", lambda: None)
    monkeypatch.setattr(service, "has_audio_stream", lambda path: False)
    monkeypatch.setattr(service, "_get_media_dimensions", lambda path: (320, 240))
    if invalid_duration is None:
        monkeypatch.setattr(
            service,
            "_get_video_duration",
            MagicMock(side_effect=OSError("ffprobe failed")),
        )
    else:
        monkeypatch.setattr(service, "_get_video_duration", lambda path: invalid_duration)
    monkeypatch.setattr(service, "_run_subtitle_command", runner)

    with pytest.raises(RuntimeError, match="valid video duration"):
        service.burn_subtitles(
            str(source),
            str(subtitle),
            str(output),
            font="Arial",
            position="bottom",
            color="#FFFFFF",
            size=28,
            stroke_color="#000000",
            stroke_width=1.5,
            cues=[],
        )

    runner.assert_not_called()
    replace.assert_not_called()
    assert output.read_bytes() == b"original"


def _read_frame(video: Path, timestamp: float, output: Path) -> np.ndarray:
    (
        ffmpeg.input(str(video), ss=timestamp)
        .output(str(output), vframes=1)
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )
    return np.asarray(Image.open(output).convert("RGB"), dtype=np.float32)


def test_burn_subtitles_preserves_duration_audio_and_cue_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import morpheus_video_studio.services.video.subtitles as subtitle_module

    monkeypatch.setattr(subtitle_module, "_ffmpeg_has_subtitles_filter", lambda: False)
    source = tmp_path / "source.mp4"
    subtitle = tmp_path / "caption:it's here.srt"
    output = tmp_path / "burned.mp4"
    _make_video(source)
    subtitle.write_text(
        "1\n00:00:00,100 --> 00:00:01,000\nDynamic subtitle\n",
        encoding="utf-8",
    )

    result = VideoService().burn_subtitles(
        str(source),
        str(subtitle),
        str(output),
        font="Arial",
        position="bottom",
        color="#FFFFFF",
        size=28,
        stroke_color="#000000",
        stroke_width=1.5,
    )

    source_probe = ffmpeg.probe(str(source))
    output_probe = ffmpeg.probe(str(output))
    assert result == str(output)
    assert float(output_probe["format"]["duration"]) == pytest.approx(
        float(source_probe["format"]["duration"]), abs=0.12
    )
    assert any(stream["codec_type"] == "audio" for stream in output_probe["streams"])
    video_stream = next(
        stream for stream in output_probe["streams"] if stream["codec_type"] == "video"
    )
    assert video_stream["codec_name"] == "h264"
    assert video_stream["pix_fmt"] == "yuv420p"
    assert subtitle.exists()

    before = _read_frame(output, 0.04, tmp_path / "before.png")
    during = _read_frame(output, 0.50, tmp_path / "during.png")
    after = _read_frame(output, 1.08, tmp_path / "after.png")
    lower_half = np.s_[120:, :, :]
    subtitle_delta = np.abs(during[lower_half] - before[lower_half]).mean()
    post_cue_delta = np.abs(after[lower_half] - before[lower_half]).mean()
    assert subtitle_delta > 1.0
    assert post_cue_delta < subtitle_delta * 0.5
