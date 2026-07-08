from pathlib import Path

import ffmpeg
import pytest

from morpheus_video_studio.services.restyle import (
    AI_RESTYLE_MAX_SECONDS,
    apply_filter_style,
    build_ai_restyle_graph,
    get_filter_style,
    list_filter_styles,
    probe_video,
    run_ai_restyle,
    working_size,
)


def _make_video(path: Path, duration: float = 4.0) -> None:
    video_in = ffmpeg.input(f"testsrc=size=320x240:rate=24", f="lavfi", t=duration)
    audio_in = ffmpeg.input("sine=frequency=440:sample_rate=44100", f="lavfi", t=duration)
    (
        ffmpeg.output(
            video_in.video, audio_in.audio, str(path),
            vcodec="libx264", acodec="aac", pix_fmt="yuv420p", preset="ultrafast",
        )
        .overwrite_output()
        .run(capture_stdout=True, capture_stderr=True)
    )


def test_filter_style_registry_is_complete() -> None:
    styles = list_filter_styles()
    ids = {style["id"] for style in styles}
    assert {"ghibli_warm", "film", "ink_wash", "cyber_neon", "vhs", "bw_film"} <= ids
    for style in styles:
        assert style["vf"], f"{style['id']} 缺少滤镜链"
    with pytest.raises(KeyError):
        get_filter_style("nope")


def test_apply_filter_style_full_and_preview(tmp_path: Path) -> None:
    source = tmp_path / "src.mp4"
    _make_video(source, duration=4.0)

    full = apply_filter_style(source, "ghibli_warm", tmp_path / "full.mp4")
    info = probe_video(full)
    assert 3.5 <= info["duration"] <= 4.5
    assert info["has_audio"]

    preview = apply_filter_style(source, "film", tmp_path / "prev.mp4", preview_seconds=2)
    assert probe_video(preview)["duration"] <= 2.6


def test_every_filter_style_chain_is_valid_ffmpeg(tmp_path: Path) -> None:
    source = tmp_path / "src.mp4"
    _make_video(source, duration=1.0)
    for style in list_filter_styles():
        out = apply_filter_style(source, style["id"], tmp_path / f"{style['id']}.mp4", preview_seconds=1)
        assert Path(out).stat().st_size > 0


def test_working_size_scales_and_aligns() -> None:
    assert working_size(1920, 1080) == (512, 288)
    assert working_size(1080, 1920) == (288, 512)
    w, h = working_size(400, 300)  # already under cap: keep, align to /8
    assert w % 8 == 0 and h % 8 == 0
    assert abs(w - 400) <= 8 and abs(h - 300) <= 8


def test_ai_graph_wiring() -> None:
    graph = build_ai_restyle_graph(
        "/tmp/in.mp4", "ghibli style", width=512, height=288, denoise=0.55
    )
    assert graph["1"]["inputs"]["force_rate"] == 10.0
    assert graph["3"]["inputs"]["lora_name"] == "lcm-lora-sdv15.safetensors"
    assert graph["5"]["inputs"]["context_options"] == ["4", 0]
    assert graph["9"]["class_type"] == "ControlNetLoaderAdvanced"
    assert graph["10"]["inputs"]["control_net"] == ["9", 0]
    assert graph["12"]["inputs"]["sampler_name"] == "lcm"
    assert graph["12"]["inputs"]["denoise"] == 0.55
    # latents come from the source frames (vid2vid), not empty noise
    assert graph["12"]["inputs"]["latent_image"] == ["11", 0]


def test_ai_restyle_rejects_long_videos(tmp_path: Path) -> None:
    source = tmp_path / "long.mp4"
    _make_video(source, duration=AI_RESTYLE_MAX_SECONDS + 5)
    with pytest.raises(ValueError, match="限"):
        run_ai_restyle(source, "style", tmp_path / "out.mp4")
