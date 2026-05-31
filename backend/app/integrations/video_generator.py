from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from app.integrations.writing import video_script


ROOT_DIR = Path(__file__).resolve().parents[3]
STORAGE_DIR = ROOT_DIR / "storage" / "generated"
PUBLIC_PREFIX = "/outputs"


class VideoGenerateRequest(BaseModel):
    title: str = "Morpheus Video Studio"
    topic: str = ""
    script: str = ""
    aspect: str = "portrait"
    seconds_per_scene: float = Field(default=3.2, ge=1.5, le=8)


class VideoGenerateResult(BaseModel):
    ok: bool
    task_id: str
    message: str
    video_url: str = ""
    video_path: str = ""
    script: str = ""
    scenes: list[str] = Field(default_factory=list)


def _resolution(aspect: str) -> tuple[int, int]:
    if aspect == "landscape":
        return 1280, 720
    if aspect == "square":
        return 1080, 1080
    return 1080, 1920


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _clean_line(line: str) -> str:
    line = re.sub(r"^\s*\d+[\.、)]\s*", "", line)
    return line.strip()


def split_scenes(script: str) -> list[str]:
    lines = [_clean_line(line) for line in script.splitlines() if _clean_line(line)]
    if len(lines) <= 1:
        lines = [
            item.strip()
            for item in re.split(r"(?<=[。！？!?；;])\s*", script)
            if item.strip()
        ]
    return lines[:8] or ["Morpheus Video Studio 已准备好生成第一条短视频。"]


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width > max_width and current:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _render_slide(path: Path, title: str, scene: str, index: int, total: int, size: tuple[int, int]) -> None:
    width, height = size
    palette = [
        ((246, 248, 250), (29, 35, 44), (199, 223, 77)),
        ((242, 245, 241), (36, 42, 38), (76, 132, 112)),
        ((249, 246, 240), (41, 38, 33), (183, 104, 76)),
        ((242, 244, 248), (31, 38, 52), (74, 114, 182)),
    ]
    bg, ink, accent = palette[index % len(palette)]
    image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image)
    title_font = _font(max(42, width // 20))
    scene_font = _font(max(48, width // 18))
    small_font = _font(max(24, width // 42))

    margin = int(width * 0.075)
    draw.rounded_rectangle(
        (margin, margin, width - margin, margin + 18),
        radius=9,
        fill=accent,
    )
    draw.text((margin, margin + 48), title[:40], font=title_font, fill=ink)
    draw.text((margin, margin + 120), f"{index + 1:02d} / {total:02d}", font=small_font, fill=accent)

    wrapped = _wrap_text(draw, scene, scene_font, width - margin * 2)
    line_height = int(scene_font.size * 1.5)
    block_height = line_height * len(wrapped)
    y = max(margin + 220, int((height - block_height) * 0.48))
    for line in wrapped:
        draw.text((margin, y), line, font=scene_font, fill=ink)
        y += line_height

    footer = "Morpheus Video Studio"
    footer_box = draw.textbbox((0, 0), footer, font=small_font)
    draw.text((width - margin - footer_box[2], height - margin - 36), footer, font=small_font, fill=(93, 103, 116))
    image.save(path)


def _write_concat_file(path: Path, slides: list[Path], seconds_per_scene: float) -> None:
    lines: list[str] = []
    for slide in slides:
        lines.append(f"file '{slide.as_posix()}'")
        lines.append(f"duration {seconds_per_scene:.2f}")
    lines.append(f"file '{slides[-1].as_posix()}'")
    path.write_text("\n".join(lines), encoding="utf-8")


def generate_local_video(payload: VideoGenerateRequest) -> VideoGenerateResult:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return VideoGenerateResult(ok=False, task_id="", message="ffmpeg is required but was not found.")

    task_id = uuid.uuid4().hex[:12]
    task_dir = STORAGE_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    script = payload.script.strip() or video_script(payload.topic or payload.title)
    scenes = split_scenes(script)
    size = _resolution(payload.aspect)
    slides: list[Path] = []
    for index, scene in enumerate(scenes):
        slide_path = task_dir / f"scene-{index + 1:02d}.png"
        _render_slide(slide_path, payload.title, scene, index, len(scenes), size)
        slides.append(slide_path)

    concat_file = task_dir / "slides.txt"
    output_file = task_dir / "final.mp4"
    metadata_file = task_dir / "metadata.json"
    _write_concat_file(concat_file, slides, payload.seconds_per_scene)

    command = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-shortest",
        "-vf",
        "format=yuv420p",
        "-c:v",
        "libx264",
        "-r",
        "30",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(output_file),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if completed.returncode != 0:
        return VideoGenerateResult(
            ok=False,
            task_id=task_id,
            message=completed.stderr[-800:] or "ffmpeg failed.",
            script=script,
            scenes=scenes,
        )

    metadata_file.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "title": payload.title,
                "script": script,
                "scenes": scenes,
                "video": str(output_file),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return VideoGenerateResult(
        ok=True,
        task_id=task_id,
        message="Video generated.",
        video_url=f"{PUBLIC_PREFIX}/{task_id}/final.mp4",
        video_path=str(output_file),
        script=script,
        scenes=scenes,
    )
