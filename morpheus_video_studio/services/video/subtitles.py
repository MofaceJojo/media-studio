# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Final-video subtitle rendering with FFmpeg/libass."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import uuid
from functools import lru_cache
from math import ceil, isfinite
from pathlib import Path
from typing import Sequence

import ffmpeg
from PIL import Image, ImageDraw, ImageFont

from morpheus_video_studio.utils.subtitle_export import SubtitleCue

_HEX_COLOR = re.compile(r"^#?([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$")
_ALIGNMENTS = {"bottom": 2, "center": 5, "top": 8}
_SRT_TIME = re.compile(
    r"^(\d+):(\d+):(\d+)[,.](\d+)\s+-->\s+"
    r"(\d+):(\d+):(\d+)[,.](\d+)$"
)


def _ass_color(color: str) -> str:
    """Convert CSS RRGGBB/RRGGBBAA into ASS AABBGGRR."""
    match = _HEX_COLOR.fullmatch((color or "").strip())
    if not match:
        raise ValueError(f"Invalid subtitle color: {color!r}")
    rgb, css_alpha = match.groups()
    red, green, blue = rgb[0:2], rgb[2:4], rgb[4:6]
    ass_alpha = 0 if css_alpha is None else 255 - int(css_alpha, 16)
    return f"&H{ass_alpha:02X}{blue.upper()}{green.upper()}{red.upper()}"


def _subtitle_style(
    *,
    font: str,
    position: str,
    color: str,
    size: int,
    stroke_color: str,
    stroke_width: float,
) -> str:
    """Build the libass force_style value from storyboard configuration."""
    safe_font = re.sub(r"[,\r\n]", " ", (font or "").strip()) or "sans-serif"
    alignment = _ALIGNMENTS.get(position, _ALIGNMENTS["bottom"])
    return ",".join(
        [
            f"FontName={safe_font}",
            f"FontSize={max(int(size), 1)}",
            f"PrimaryColour={_ass_color(color)}",
            f"OutlineColour={_ass_color(stroke_color)}",
            "BorderStyle=1",
            f"Outline={max(float(stroke_width), 0.0):g}",
            "Shadow=0",
            f"Alignment={alignment}",
            "MarginV=36",
        ]
    )


def _burn_command(
    video: str,
    subtitle_file: str,
    output: str,
    force_style: str,
    *,
    has_audio: bool,
) -> list[str]:
    """Compile an argv-safe FFmpeg graph; ffmpeg-python escapes filter values."""
    source = ffmpeg.input(video)
    rendered_video = source.video.filter(
        "subtitles",
        filename=subtitle_file,
        force_style=force_style,
    )
    streams = [rendered_video]
    output_options = {
        "vcodec": "libx264",
        "pix_fmt": "yuv420p",
        "movflags": "+faststart",
    }
    if has_audio:
        streams.append(source.audio)
        output_options.update(acodec="aac", audio_bitrate="192k")
    graph = ffmpeg.output(*streams, output, **output_options).overwrite_output()
    return ffmpeg.compile(graph)


@lru_cache(maxsize=1)
def _ffmpeg_has_subtitles_filter() -> bool:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"],
        capture_output=True,
        text=True,
        check=False,
    )
    return any(
        line.split()[1:2] == ["subtitles"] for line in result.stdout.splitlines()
    )


def _srt_seconds(parts: tuple[str, str, str, str]) -> float:
    hours, minutes, seconds, millis = (int(value) for value in parts)
    return hours * 3600 + minutes * 60 + seconds + millis / (10 ** len(parts[3]))


def _read_srt_cues(path: str) -> list[SubtitleCue]:
    """Parse the SRT shape emitted by export_srt_cues for standalone callers."""
    content = Path(path).read_text(encoding="utf-8-sig")
    cues: list[SubtitleCue] = []
    for block in re.split(r"\r?\n\s*\r?\n", content.strip()):
        lines = block.splitlines()
        if len(lines) < 3:
            continue
        match = _SRT_TIME.fullmatch(lines[1].strip())
        if not match:
            continue
        values = match.groups()
        text = "\n".join(lines[2:]).strip()
        if text:
            cues.append(
                SubtitleCue(
                    text,
                    _srt_seconds(values[:4]),
                    _srt_seconds(values[4:]),
                )
            )
    return cues


def _load_font(font: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    requested = (font or "").strip()
    candidates = [requested]
    if requested and not Path(requested).suffix:
        candidates.extend([f"{requested}.ttf", f"{requested}.ttc"])
    candidates.extend(
        [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "DejaVuSans.ttf",
        ]
    )
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _rgba(color: str) -> tuple[int, int, int, int]:
    match = _HEX_COLOR.fullmatch((color or "").strip())
    if not match:
        raise ValueError(f"Invalid subtitle color: {color!r}")
    rgb, alpha = match.groups()
    return (
        int(rgb[0:2], 16),
        int(rgb[2:4], 16),
        int(rgb[4:6], 16),
        int(alpha, 16) if alpha else 255,
    )


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    stroke_width: int,
    line_limit: int | None = None,
) -> tuple[str, bool]:
    lines: list[str] = []
    paragraphs = (text or "").splitlines() or [""]
    for paragraph_index, paragraph in enumerate(paragraphs):
        current = ""
        for character_index, character in enumerate(paragraph):
            candidate = current + character
            bbox = draw.textbbox(
                (0, 0), candidate, font=font, stroke_width=stroke_width
            )
            if current and bbox[2] - bbox[0] > max_width:
                lines.append(current)
                if line_limit is not None and len(lines) >= line_limit:
                    return "\n".join(lines), True
                current = character
            else:
                current = candidate
        lines.append(current)
        has_more_text = paragraph_index < len(paragraphs) - 1
        if line_limit is not None and len(lines) >= line_limit and has_more_text:
            return "\n".join(lines), True
    return "\n".join(lines), False


def _ellipsize_line(
    draw: ImageDraw.ImageDraw,
    line: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    stroke_width: int,
) -> str:
    visible = line.rstrip()
    while visible:
        candidate = visible + "…"
        bbox = draw.textbbox(
            (0, 0), candidate, font=font, stroke_width=stroke_width
        )
        if bbox[2] - bbox[0] <= max_width:
            return candidate
        visible = visible[:-1]
    return "…"


def _fit_cue_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_name: str,
    requested_size: int,
    max_width: int,
    max_height: int,
    stroke_width: int,
) -> tuple[str, ImageFont.FreeTypeFont | ImageFont.ImageFont, int, tuple[int, int, int, int]]:
    minimum_size = min(max(int(requested_size), 1), 10)
    last_result = None
    for candidate_size in range(max(int(requested_size), 1), minimum_size - 1, -2):
        font = _load_font(font_name, candidate_size)
        spacing = max(int(candidate_size * 0.15), 2)
        line_bbox = draw.textbbox(
            (0, 0), "Ag", font=font, stroke_width=stroke_width
        )
        line_height = max(line_bbox[3] - line_bbox[1] + spacing, 1)
        line_limit = max(max_height // line_height, 1) + 1
        wrapped, truncated = _wrap_text(
            draw,
            text,
            font,
            max_width,
            stroke_width,
            line_limit=line_limit,
        )
        bbox = draw.multiline_textbbox(
            (0, 0),
            wrapped,
            font=font,
            align="center",
            spacing=spacing,
            stroke_width=stroke_width,
        )
        last_result = (wrapped, font, spacing, bbox, truncated)
        if (
            not truncated
            and bbox[2] - bbox[0] <= max_width
            and bbox[3] - bbox[1] <= max_height
        ):
            return wrapped, font, spacing, bbox

    assert last_result is not None
    wrapped, font, spacing, _, truncated = last_result
    lines = wrapped.splitlines() or [""]
    while lines:
        candidate_lines = list(lines)
        if truncated:
            candidate_lines[-1] = _ellipsize_line(
                draw,
                candidate_lines[-1],
                font,
                max_width,
                stroke_width,
            )
        candidate = "\n".join(candidate_lines)
        bbox = draw.multiline_textbbox(
            (0, 0),
            candidate,
            font=font,
            align="center",
            spacing=spacing,
            stroke_width=stroke_width,
        )
        if bbox[2] - bbox[0] <= max_width and bbox[3] - bbox[1] <= max_height:
            return candidate, font, spacing, bbox
        lines.pop()
        truncated = True
    fallback = "…"
    bbox = draw.textbbox((0, 0), fallback, font=font, stroke_width=stroke_width)
    return fallback, font, spacing, bbox


def _render_cue_image(
    cue: SubtitleCue,
    path: Path,
    *,
    width: int,
    height: int,
    font: str,
    position: str,
    color: str,
    size: int,
    stroke_color: str,
    stroke_width: float,
) -> None:
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    outline = max(int(ceil(float(stroke_width))), 0)
    horizontal_margin = max(int(width * 0.05), 8)
    vertical_margin = max(int(height * 0.08), 8)
    wrapped_text, resolved_font, spacing, bbox = _fit_cue_text(
        draw,
        cue.text,
        font,
        max(int(size), 1),
        width - (2 * horizontal_margin),
        max(int(height * 0.5), 1),
        outline,
    )
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) / 2 - bbox[0]
    if position == "top":
        y = vertical_margin - bbox[1]
    elif position == "center":
        y = (height - text_height) / 2 - bbox[1]
    else:
        y = height - vertical_margin - text_height - bbox[1]
    draw.multiline_text(
        (x, y),
        wrapped_text,
        font=resolved_font,
        fill=_rgba(color),
        align="center",
        spacing=spacing,
        stroke_width=outline,
        stroke_fill=_rgba(stroke_color),
    )
    canvas.save(path)


def _concat_path(path: str) -> str:
    return str(Path(path).absolute()).replace("'", "'\\''")


def _write_overlay_manifest(
    overlays: Sequence[tuple[str, float, float]],
    *,
    total_duration: float,
    manifest_path: Path,
    blank_path: Path,
) -> Path:
    """Describe any number of cues through one concat-demuxer input."""
    entries: list[tuple[str, float]] = []
    cursor = 0.0
    timeline_end = max(float(total_duration), 0.0)
    for image_path, raw_start, raw_end in sorted(overlays, key=lambda item: item[1]):
        start = min(max(float(raw_start), cursor, 0.0), timeline_end)
        end = min(max(float(raw_end), start), timeline_end)
        if start > cursor:
            entries.append((str(blank_path), start - cursor))
            cursor = start
        if end > start:
            entries.append((image_path, end - start))
            cursor = end
    if total_duration > cursor:
        entries.append((str(blank_path), total_duration - cursor))
    if not entries:
        entries.append((str(blank_path), max(float(total_duration), 0.001)))

    lines = ["ffconcat version 1.0"]
    for image_path, duration in entries:
        lines.extend(
            [
                f"file '{_concat_path(image_path)}'",
                f"duration {max(duration, 0.001):.6f}",
            ]
        )
    lines.append(f"file '{_concat_path(entries[-1][0])}'")
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


def _overlay_video_command(manifest: str, output: str) -> list[str]:
    """Encode the concat timeline as one lossless video with alpha."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        manifest,
        "-fps_mode",
        "vfr",
        "-c:v",
        "qtrle",
        "-pix_fmt",
        "argb",
        output,
        "-y",
    ]


def _single_overlay_command(
    video: str,
    overlay_video: str,
    output: str,
    *,
    has_audio: bool,
) -> list[str]:
    source = ffmpeg.input(video)
    overlay_source = ffmpeg.input(overlay_video)
    rendered_video = ffmpeg.overlay(
        source.video,
        overlay_source.video,
        eof_action="pass",
        shortest=0,
    )
    streams = [rendered_video]
    output_options = {
        "vcodec": "libx264",
        "pix_fmt": "yuv420p",
        "movflags": "+faststart",
    }
    if has_audio:
        streams.append(source.audio)
        output_options.update(acodec="aac", audio_bitrate="192k")
    return ffmpeg.compile(
        ffmpeg.output(*streams, output, **output_options).overwrite_output()
    )


class SubtitleMixin:
    """Burn timed subtitles into a video while preserving its audio stream."""

    def burn_subtitles(
        self,
        video: str,
        subtitle_file: str,
        output: str,
        *,
        font: str,
        position: str,
        color: str,
        size: int,
        stroke_color: str,
        stroke_width: float,
        cues: Sequence[SubtitleCue] | None = None,
    ) -> str:
        self._ensure_ffmpeg()
        video_path = Path(video)
        subtitle_path = Path(subtitle_file)
        output_path = Path(output)
        if not video_path.is_file():
            raise FileNotFoundError(f"Video not found: {video}")
        if not subtitle_path.is_file():
            raise FileNotFoundError(f"Subtitle file not found: {subtitle_file}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = output_path.suffix or ".mp4"
        temporary_path = output_path.with_name(
            f".{output_path.stem}.{uuid.uuid4().hex}.tmp{suffix}"
        )
        style = _subtitle_style(
            font=font,
            position=position,
            color=color,
            size=size,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
        )
        has_audio = self.has_audio_stream(str(video_path))

        try:
            if _ffmpeg_has_subtitles_filter():
                command = _burn_command(
                    str(video_path),
                    str(subtitle_path),
                    str(temporary_path),
                    style,
                    has_audio=has_audio,
                )
                self._run_subtitle_command(command)
            else:
                resolved_cues = list(cues) if cues is not None else _read_srt_cues(str(subtitle_path))
                try:
                    video_duration = float(self._get_video_duration(str(video_path)))
                except Exception as exc:
                    raise RuntimeError(
                        "Could not determine a valid video duration for subtitle fallback"
                    ) from exc
                if not isfinite(video_duration) or video_duration <= 0:
                    raise RuntimeError(
                        "Could not determine a valid video duration for subtitle fallback"
                    )
                width, height = self._get_media_dimensions(str(video_path))
                with tempfile.TemporaryDirectory(
                    prefix="mvs_subtitles_", dir=output_path.parent
                ) as temporary_directory:
                    temporary_directory_path = Path(temporary_directory)
                    blank_path = temporary_directory_path / "blank.png"
                    Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(blank_path)
                    overlays = []
                    for index, cue in enumerate(resolved_cues):
                        image_path = temporary_directory_path / f"cue_{index:04d}.png"
                        _render_cue_image(
                            cue,
                            image_path,
                            width=width,
                            height=height,
                            font=font,
                            position=position,
                            color=color,
                            size=size,
                            stroke_color=stroke_color,
                            stroke_width=stroke_width,
                        )
                        overlays.append((str(image_path), cue.start, cue.end))
                    manifest_path = _write_overlay_manifest(
                        overlays,
                        total_duration=video_duration,
                        manifest_path=temporary_directory_path / "timeline.ffconcat",
                        blank_path=blank_path,
                    )
                    overlay_video_path = temporary_directory_path / "overlay.mov"
                    self._run_subtitle_command(
                        _overlay_video_command(str(manifest_path), str(overlay_video_path))
                    )
                    command = _single_overlay_command(
                        str(video_path),
                        str(overlay_video_path),
                        str(temporary_path),
                        has_audio=has_audio,
                    )
                    self._run_subtitle_command(command)
            os.replace(temporary_path, output_path)
        finally:
            temporary_path.unlink(missing_ok=True)
        return str(output_path)

    @staticmethod
    def _run_subtitle_command(command: list[str]) -> None:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            error = (completed.stderr or completed.stdout or "Unknown FFmpeg error").strip()
            raise RuntimeError(f"Failed to burn subtitles: {error}")
