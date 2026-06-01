from __future__ import annotations

import json
import random
import shutil
import subprocess
import uuid
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "output" / "moneyprinter_plus"
WORK_DIR = ROOT / "temp" / "moneyprinter_plus"
MATERIAL_DIR = ROOT / "data" / "stock_materials"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS

PUBLISH_PLATFORMS = {
    "douyin": {
        "name": "抖音",
        "region": "CN",
        "upload_url": "https://creator.douyin.com/creator-micro/content/upload",
        "adapter": "browser",
        "api_ready": False,
    },
    "kuaishou": {
        "name": "快手",
        "region": "CN",
        "upload_url": "https://cp.kuaishou.com/article/publish/video",
        "adapter": "browser",
        "api_ready": False,
    },
    "xiaohongshu": {
        "name": "小红书",
        "region": "CN",
        "upload_url": "https://creator.xiaohongshu.com/publish/publish?source=official",
        "adapter": "browser",
        "api_ready": False,
    },
    "shipinhao": {
        "name": "视频号",
        "region": "CN",
        "upload_url": "https://channels.weixin.qq.com/platform/post/create",
        "adapter": "browser",
        "api_ready": False,
    },
    "bilibili": {
        "name": "Bilibili",
        "region": "CN",
        "upload_url": "https://member.bilibili.com/platform/upload/video/frame",
        "adapter": "browser",
        "api_ready": False,
    },
    "youtube": {
        "name": "YouTube",
        "region": "Global",
        "upload_url": "https://studio.youtube.com",
        "adapter": "api_or_browser",
        "api_ready": False,
    },
    "x": {
        "name": "X",
        "region": "Global",
        "upload_url": "https://x.com/compose/post",
        "adapter": "api_or_browser",
        "api_ready": False,
    },
    "tiktok": {
        "name": "TikTok",
        "region": "Global",
        "upload_url": "https://www.tiktok.com/upload",
        "adapter": "api_or_browser",
        "api_ready": False,
    },
    "instagram": {
        "name": "Instagram",
        "region": "Global",
        "upload_url": "https://www.instagram.com",
        "adapter": "api_or_browser",
        "api_ready": False,
    },
    "facebook": {
        "name": "Facebook",
        "region": "Global",
        "upload_url": "https://www.facebook.com",
        "adapter": "api_or_browser",
        "api_ready": False,
    },
}


def get_publish_platforms() -> dict[str, dict[str, str | bool]]:
    """Return registered publish platforms.

    New integrations should be added here first, then implemented by a
    browser/API adapter keyed by the same platform id.
    """
    return PUBLISH_PLATFORMS.copy()


def get_platform_options() -> list[str]:
    """Return platform ids in UI order."""
    return list(PUBLISH_PLATFORMS.keys())


def format_platform(platform_id: str) -> str:
    """Human-readable platform label for UI controls."""
    platform = PUBLISH_PLATFORMS.get(platform_id, {})
    name = platform.get("name", platform_id)
    region = platform.get("region", "")
    return f"{name} · {region}" if region else str(name)


@dataclass
class StockMaterial:
    provider: str
    title: str
    url: str
    duration: float
    width: int
    height: int


def _ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required.")
    return ffmpeg


def _ffprobe_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
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
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return 0.0


def media_files(directory: str) -> list[Path]:
    root = Path(directory).expanduser()
    if not root.exists():
        return []
    return [
        item
        for item in sorted(root.rglob("*"))
        if item.is_file() and item.suffix.lower() in MEDIA_EXTENSIONS
    ]


def _normalize_clip(source: Path, target: Path, size: tuple[int, int], fps: int, duration: float) -> Path:
    ffmpeg = _ffmpeg()
    width, height = size
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,format=yuv420p"
    )
    if source.suffix.lower() in IMAGE_EXTENSIONS:
        command = [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-i",
            str(source),
            "-t",
            f"{duration:.2f}",
            "-r",
            str(fps),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ]
    else:
        command = [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-t",
            f"{duration:.2f}",
            "-r",
            str(fps),
            "-vf",
            vf,
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-1200:] or f"Failed to normalize {source}")
    return target


def _concat_clips(clips: list[Path], output: Path, bgm_path: str = "", bgm_volume: float = 0.25) -> Path:
    ffmpeg = _ffmpeg()
    output.parent.mkdir(parents=True, exist_ok=True)
    list_file = output.with_suffix(".txt")
    list_file.write_text("\n".join(f"file '{clip.as_posix()}'" for clip in clips) + "\n", encoding="utf-8")
    base_output = output.with_name(f"{output.stem}-base.mp4")
    completed = subprocess.run(
        [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(base_output)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr[-1200:] or "Failed to concatenate clips.")

    music = Path(bgm_path).expanduser() if bgm_path else None
    if music and music.exists():
        completed = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(base_output),
                "-stream_loop",
                "-1",
                "-i",
                str(music),
                "-filter_complex",
                f"[1:a]volume={bgm_volume}[bgm];[0:a][bgm]amix=duration=first:inputs=2[a]",
                "-map",
                "0:v:0",
                "-map",
                "[a]",
                "-shortest",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=240,
        )
        if completed.returncode == 0:
            return output

    shutil.move(base_output, output)
    return output


def merge_media(
    files: list[str],
    output_name: str = "",
    size: tuple[int, int] = (1080, 1920),
    fps: int = 30,
    clip_duration: float = 5.0,
    bgm_path: str = "",
    bgm_volume: float = 0.25,
) -> Path:
    sources = [Path(item).expanduser() for item in files if item.strip()]
    sources = [path for path in sources if path.exists() and path.suffix.lower() in MEDIA_EXTENSIONS]
    if not sources:
        raise ValueError("No valid media files selected.")
    task_dir = WORK_DIR / uuid.uuid4().hex[:10]
    task_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    for index, source in enumerate(sources):
        duration = clip_duration if source.suffix.lower() in IMAGE_EXTENSIONS else min(max(_ffprobe_duration(source), clip_duration), clip_duration)
        clips.append(_normalize_clip(source, task_dir / f"clip-{index + 1:03d}.mp4", size, fps, duration))
    name = output_name.strip() or f"merge-{uuid.uuid4().hex[:8]}.mp4"
    if not name.endswith(".mp4"):
        name += ".mp4"
    return _concat_clips(clips, OUTPUT_DIR / name, bgm_path, bgm_volume)


def mix_from_scene_dirs(
    scene_dirs: list[str],
    count: int = 1,
    size: tuple[int, int] = (1080, 1920),
    fps: int = 30,
    clip_duration: float = 5.0,
    bgm_path: str = "",
    bgm_volume: float = 0.25,
) -> list[Path]:
    pools = [media_files(item) for item in scene_dirs if item.strip()]
    pools = [pool for pool in pools if pool]
    if not pools:
        raise ValueError("No valid scene media folders.")
    results = []
    for item_index in range(max(1, count)):
        picked = [str(random.choice(pool)) for pool in pools]
        results.append(
            merge_media(
                picked,
                output_name=f"mix-{uuid.uuid4().hex[:8]}-{item_index + 1:02d}.mp4",
                size=size,
                fps=fps,
                clip_duration=clip_duration,
                bgm_path=bgm_path,
                bgm_volume=bgm_volume,
            )
        )
    return results


async def search_stock_materials(
    provider: str,
    api_key: str,
    query: str,
    orientation: str = "portrait",
    per_page: int = 8,
) -> list[StockMaterial]:
    if provider == "pexels":
        params = urlencode({"query": query, "orientation": orientation, "per_page": per_page})
        headers = {"Authorization": api_key}
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=True) as client:
            response = await client.get(f"https://api.pexels.com/videos/search?{params}", headers=headers)
            response.raise_for_status()
        items = []
        for video in response.json().get("videos", []):
            files = sorted(video.get("video_files", []), key=lambda f: f.get("width", 0), reverse=True)
            if not files:
                continue
            best = files[0]
            items.append(StockMaterial("pexels", video.get("url", "Pexels video"), best["link"], video.get("duration", 0), best.get("width", 0), best.get("height", 0)))
        return items

    params = urlencode({"key": api_key, "q": query, "per_page": per_page})
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=True) as client:
        response = await client.get(f"https://pixabay.com/api/videos/?{params}")
        response.raise_for_status()
    items = []
    for video in response.json().get("hits", []):
        variants = video.get("videos", {})
        best = variants.get("large") or variants.get("medium") or variants.get("small") or variants.get("tiny")
        if best:
            items.append(StockMaterial("pixabay", video.get("pageURL", "Pixabay video"), best["url"], video.get("duration", 0), best.get("width", 0), best.get("height", 0)))
    return items


async def download_material(url: str, provider: str = "stock") -> Path:
    MATERIAL_DIR.mkdir(parents=True, exist_ok=True)
    target = MATERIAL_DIR / f"{provider}-{uuid.uuid4().hex[:10]}.mp4"
    async with httpx.AsyncClient(timeout=90, follow_redirects=True, verify=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with target.open("wb") as file:
                async for chunk in response.aiter_bytes(1024 * 256):
                    file.write(chunk)
    return target


def create_publish_queue(content_dir: str, platforms: list[str], title_prefix: str, tags: str, auto_open: bool) -> Path:
    root = Path(content_dir).expanduser()
    if not root.exists():
        raise ValueError("Content directory does not exist.")
    videos = [item for item in sorted(root.iterdir()) if item.suffix.lower() in {".mp4", ".mov"}]
    tasks = []
    platform_details = {
        platform: PUBLISH_PLATFORMS[platform]
        for platform in platforms
        if platform in PUBLISH_PLATFORMS
    }
    for video in videos:
        text_file = video.with_suffix(".txt")
        tasks.append({
            "video": str(video),
            "text": str(text_file) if text_file.exists() else "",
            "title": f"{title_prefix}{video.stem}",
            "tags": tags.split(),
            "platforms": list(platform_details.keys()),
            "platform_details": platform_details,
        })
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    queue_path = OUTPUT_DIR / "publish_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "tasks": tasks,
                "platforms": platform_details,
                "adapter_contract": {
                    "browser": "Use upload_url with an authenticated browser session.",
                    "api_or_browser": "Reserved for official API upload adapter or browser automation.",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if auto_open:
        for platform in platform_details.values():
            url = platform.get("upload_url")
            if url:
                webbrowser.open(str(url))
    return queue_path


def material_to_dicts(items: list[StockMaterial]) -> list[dict]:
    return [asdict(item) for item in items]
