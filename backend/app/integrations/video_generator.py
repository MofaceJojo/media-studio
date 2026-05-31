from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from app.integrations.materials import MaterialSearchRequest, search_materials
from app.integrations.writing import WritingRequest, read_source_files, run_writing_tool, video_script


ROOT_DIR = Path(__file__).resolve().parents[3]
STORAGE_DIR = ROOT_DIR / "storage" / "generated"
PUBLIC_PREFIX = "/outputs"


class VideoGenerateRequest(BaseModel):
    title: str = "Morpheus Video Studio"
    topic: str = ""
    script: str = ""
    aspect: str = "portrait"
    seconds_per_scene: float = Field(default=3.2, ge=1.5, le=8)
    voice_provider: str = "edge"
    voice: str = "zh-CN-XiaoxiaoNeural"
    local_voice_url: str = ""
    enable_subtitles: bool = True
    local_media_paths: str = ""
    source_file_paths: str = ""
    source_file_skill: str = "video_script"
    use_online_materials: bool = False
    online_material_provider: str = "pexels"
    online_material_api_keys: list[str] = Field(default_factory=list)
    online_material_query: str = ""


class VideoGenerateResult(BaseModel):
    ok: bool
    task_id: str
    message: str
    video_url: str = ""
    video_path: str = ""
    audio_path: str = ""
    subtitle_path: str = ""
    voice_provider: str = ""
    media_used: list[str] = Field(default_factory=list)
    source_files_used: list[str] = Field(default_factory=list)
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


def _render_slide(
    path: Path,
    title: str,
    scene: str,
    index: int,
    total: int,
    size: tuple[int, int],
    show_caption: bool,
    background_path: Path | None = None,
) -> None:
    width, height = size
    palette = [
        ((246, 248, 250), (29, 35, 44), (199, 223, 77)),
        ((242, 245, 241), (36, 42, 38), (76, 132, 112)),
        ((249, 246, 240), (41, 38, 33), (183, 104, 76)),
        ((242, 244, 248), (31, 38, 52), (74, 114, 182)),
    ]
    bg, ink, accent = palette[index % len(palette)]
    if background_path and background_path.exists():
        source = Image.open(background_path).convert("RGB")
        scale = max(width / source.width, height / source.height)
        resized = source.resize((int(source.width * scale), int(source.height * scale)))
        left = max(0, (resized.width - width) // 2)
        top = max(0, (resized.height - height) // 2)
        image = resized.crop((left, top, left + width, top + height))
        dim = Image.new("RGBA", size, (246, 248, 250, 72))
        image = Image.alpha_composite(image.convert("RGBA"), dim).convert("RGB")
    else:
        image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image)
    title_font = _font(max(42, width // 20))
    scene_font = _font(max(48, width // 18))
    small_font = _font(max(24, width // 42))
    caption_font = _font(max(32, width // 28))

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

    if show_caption:
        caption_lines = _wrap_text(draw, scene, caption_font, width - margin * 2)
        caption_lines = caption_lines[:2]
        caption_line_height = int(caption_font.size * 1.32)
        caption_height = caption_line_height * len(caption_lines) + 42
        caption_top = height - margin - 92 - caption_height
        overlay = Image.new("RGBA", size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            (margin, caption_top, width - margin, caption_top + caption_height),
            radius=18,
            fill=(18, 22, 29, 210),
        )
        image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(image)
        caption_y = caption_top + 22
        for line in caption_lines:
            line_box = draw.textbbox((0, 0), line, font=caption_font)
            draw.text(((width - line_box[2]) / 2, caption_y), line, font=caption_font, fill=(255, 255, 255))
            caption_y += caption_line_height

    image.save(path)


def _render_overlay(
    path: Path,
    title: str,
    scene: str,
    index: int,
    total: int,
    size: tuple[int, int],
    show_caption: bool,
) -> None:
    width, height = size
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    title_font = _font(max(42, width // 20))
    small_font = _font(max(24, width // 42))
    caption_font = _font(max(32, width // 28))
    margin = int(width * 0.075)

    draw.rounded_rectangle((0, 0, width, height), radius=0, fill=(0, 0, 0, 46))
    draw.rounded_rectangle((margin, margin, width - margin, margin + 18), radius=9, fill=(199, 223, 77, 235))
    draw.text((margin, margin + 48), title[:40], font=title_font, fill=(255, 255, 255, 245))
    draw.text((margin, margin + 120), f"{index + 1:02d} / {total:02d}", font=small_font, fill=(213, 241, 93, 245))

    if show_caption:
        caption_lines = _wrap_text(draw, scene, caption_font, width - margin * 2)
        caption_lines = caption_lines[:2]
        caption_line_height = int(caption_font.size * 1.32)
        caption_height = caption_line_height * len(caption_lines) + 42
        caption_top = height - margin - 92 - caption_height
        draw.rounded_rectangle(
            (margin, caption_top, width - margin, caption_top + caption_height),
            radius=18,
            fill=(18, 22, 29, 218),
        )
        caption_y = caption_top + 22
        for line in caption_lines:
            line_box = draw.textbbox((0, 0), line, font=caption_font)
            draw.text(((width - line_box[2]) / 2, caption_y), line, font=caption_font, fill=(255, 255, 255, 255))
            caption_y += caption_line_height

    footer = "Morpheus Video Studio"
    footer_box = draw.textbbox((0, 0), footer, font=small_font)
    draw.text((width - margin - footer_box[2], height - margin - 36), footer, font=small_font, fill=(255, 255, 255, 210))
    image.save(path)


def _write_concat_file(path: Path, slides: list[Path], seconds_per_scene: float) -> None:
    lines: list[str] = []
    for slide in slides:
        lines.append(f"file '{slide.as_posix()}'")
        lines.append(f"duration {seconds_per_scene:.2f}")
    lines.append(f"file '{slides[-1].as_posix()}'")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_video_concat_file(path: Path, clips: list[Path]) -> None:
    path.write_text(
        "\n".join(f"file '{clip.as_posix()}'" for clip in clips) + "\n",
        encoding="utf-8",
    )


def _create_image_scene(ffmpeg: str, image_path: Path, clip_path: Path, duration: float) -> bool:
    completed = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-t",
            f"{duration:.2f}",
            "-vf",
            "format=yuv420p",
            "-c:v",
            "libx264",
            "-r",
            "30",
            "-pix_fmt",
            "yuv420p",
            str(clip_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return completed.returncode == 0 and clip_path.exists()


def _create_video_scene(
    ffmpeg: str,
    media_path: Path,
    overlay_path: Path,
    clip_path: Path,
    size: tuple[int, int],
    duration: float,
) -> bool:
    width, height = size
    filter_graph = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1[bg];"
        "[bg][1:v]overlay=0:0,format=yuv420p[v]"
    )
    completed = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(media_path),
            "-i",
            str(overlay_path),
            "-t",
            f"{duration:.2f}",
            "-filter_complex",
            filter_graph,
            "-map",
            "[v]",
            "-an",
            "-c:v",
            "libx264",
            "-r",
            "30",
            "-pix_fmt",
            "yuv420p",
            str(clip_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return completed.returncode == 0 and clip_path.exists()


def _format_srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _write_srt(path: Path, scenes: list[str], seconds_per_scene: float) -> None:
    blocks: list[str] = []
    for index, scene in enumerate(scenes):
        start = index * seconds_per_scene
        end = start + seconds_per_scene
        blocks.append(
            "\n".join(
                [
                    str(index + 1),
                    f"{_format_srt_time(start)} --> {_format_srt_time(end)}",
                    scene,
                ]
            )
        )
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def _parse_media_paths(raw_paths: str) -> list[Path]:
    paths: list[Path] = []
    for item in re.split(r"[\n,]+", raw_paths):
        value = item.strip().strip('"').strip("'")
        if not value:
            continue
        path = Path(value).expanduser()
        if path.exists() and path.is_file():
            paths.append(path)
    return paths


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _is_video(path: Path) -> bool:
    return path.suffix.lower() in {".mp4", ".mov", ".m4v", ".mkv", ".webm"}


async def _download_video(url: str, path: Path, max_bytes: int = 90_000_000) -> bool:
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True, verify=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                total = 0
                with path.open("wb") as file:
                    async for chunk in response.aiter_bytes(1024 * 256):
                        total += len(chunk)
                        if total > max_bytes:
                            return False
                        file.write(chunk)
        return path.exists() and path.stat().st_size > 0
    except Exception:
        return False


async def _fetch_online_materials(payload: VideoGenerateRequest, task_dir: Path, count: int) -> list[Path]:
    keys = [key.strip() for key in payload.online_material_api_keys if key.strip()]
    if not payload.use_online_materials or not keys:
        return []
    result = await search_materials(
        MaterialSearchRequest(
            provider=payload.online_material_provider,
            api_keys=keys,
            query=payload.online_material_query or payload.topic or payload.title,
            aspect=payload.aspect,
            min_duration=max(2, int(payload.seconds_per_scene)),
        )
    )
    if not result.ok:
        return []

    paths: list[Path] = []
    for index, item in enumerate(result.items[: max(1, min(count, 4))]):
        path = task_dir / f"online-{index + 1:02d}.mp4"
        if await _download_video(item.url, path):
            paths.append(path)
    return paths


def _probe_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.exists():
        return 0.0
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        return 0.0
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return 0.0


async def _create_voiceover(payload: VideoGenerateRequest, script: str, task_dir: Path) -> tuple[Path | None, str]:
    provider = payload.voice_provider.strip() or "edge"
    if provider == "none":
        return None, "none"

    audio_path = task_dir / "voiceover.mp3"
    narration = re.sub(r"^\s*\d+[\.、)]\s*", "", script, flags=re.MULTILINE)
    narration = re.sub(r"\s+", " ", narration).strip()
    if not narration:
        return None, "none"

    if provider == "local_api":
        base_url = payload.local_voice_url.strip().rstrip("/")
        if not base_url:
            return None, "silent"
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{base_url}/tts",
                    json={"text": narration, "voice": payload.voice},
                )
                response.raise_for_status()
            audio_path.write_bytes(response.content)
            if audio_path.stat().st_size > 0:
                return audio_path, "local_api"
        except Exception:
            return None, "silent"

    try:
        import edge_tts

        communicate = edge_tts.Communicate(narration, payload.voice)
        await communicate.save(str(audio_path))
        if audio_path.exists() and audio_path.stat().st_size > 0:
            return audio_path, "edge"
    except Exception:
        return None, "silent"
    return None, "silent"


async def generate_local_video(payload: VideoGenerateRequest) -> VideoGenerateResult:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return VideoGenerateResult(ok=False, task_id="", message="ffmpeg is required but was not found.")

    task_id = uuid.uuid4().hex[:12]
    task_dir = STORAGE_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    source_file_text = ""
    source_files_used: list[str] = []
    script = payload.script.strip()
    if not script:
        source_file_text, source_files_used = read_source_files(payload.source_file_paths)
    if not script and source_file_text:
        writing = run_writing_tool(
            WritingRequest(
                mode=payload.source_file_skill,
                text=payload.topic,
                tone="clean",
                source_file_paths=payload.source_file_paths,
            )
        )
        script = writing.text
        source_files_used = writing.source_files_used
    if not script:
        script = video_script(payload.topic or payload.title)
    scenes = split_scenes(script)
    audio_path, voice_provider = await _create_voiceover(payload, script, task_dir)
    scene_seconds = payload.seconds_per_scene
    if audio_path:
        audio_duration = _probe_duration(audio_path)
        if audio_duration > 0:
            scene_seconds = max(scene_seconds, (audio_duration + 0.35) / max(1, len(scenes)))

    size = _resolution(payload.aspect)
    media_paths = _parse_media_paths(payload.local_media_paths)
    if not media_paths:
        media_paths = await _fetch_online_materials(payload, task_dir, len(scenes))
    media_used: list[str] = []
    scene_clips: list[Path] = []
    for index, scene in enumerate(scenes):
        media_path = media_paths[index % len(media_paths)] if media_paths else None
        if media_path:
            media_used.append(str(media_path))
        clip_path = task_dir / f"clip-{index + 1:02d}.mp4"
        if media_path and _is_video(media_path):
            overlay_path = task_dir / f"overlay-{index + 1:02d}.png"
            _render_overlay(
                overlay_path,
                payload.title,
                scene,
                index,
                len(scenes),
                size,
                payload.enable_subtitles,
            )
            if _create_video_scene(ffmpeg, media_path, overlay_path, clip_path, size, scene_seconds):
                scene_clips.append(clip_path)
                continue

        slide_path = task_dir / f"scene-{index + 1:02d}.png"
        background_path = media_path if media_path and _is_image(media_path) else None
        _render_slide(
            slide_path,
            payload.title,
            scene,
            index,
            len(scenes),
            size,
            payload.enable_subtitles,
            background_path,
        )
        if not _create_image_scene(ffmpeg, slide_path, clip_path, scene_seconds):
            return VideoGenerateResult(
                ok=False,
                task_id=task_id,
                message="ffmpeg failed while creating a scene clip.",
                script=script,
                scenes=scenes,
            )
        scene_clips.append(clip_path)

    concat_file = task_dir / "slides.txt"
    output_file = task_dir / "final.mp4"
    base_video_file = task_dir / "base.mp4"
    subtitle_file = task_dir / "subtitles.srt"
    metadata_file = task_dir / "metadata.json"
    _write_srt(subtitle_file, scenes, scene_seconds)

    _write_video_concat_file(concat_file, scene_clips)
    command = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(base_video_file),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if completed.returncode != 0:
        return VideoGenerateResult(
            ok=False,
            task_id=task_id,
            message=completed.stderr[-800:] or "ffmpeg failed while combining scene clips.",
            script=script,
            scenes=scenes,
        )

    command = [ffmpeg, "-y", "-i", str(base_video_file)]
    if audio_path:
        command.extend(["-i", str(audio_path)])
    else:
        command.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])
    command.extend(
        [
            "-shortest",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            str(output_file),
        ]
    )
    completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
    if completed.returncode != 0:
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(base_video_file),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-shortest",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
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
                "audio": str(audio_path) if audio_path else "",
                "subtitles": str(subtitle_file),
                "voice_provider": voice_provider,
                "media_used": media_used,
                "source_files_used": source_files_used,
                "seconds_per_scene": scene_seconds,
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
        audio_path=str(audio_path) if audio_path else "",
        subtitle_path=str(subtitle_file),
        voice_provider=voice_provider,
        media_used=media_used,
        source_files_used=source_files_used,
        script=script,
        scenes=scenes,
    )
