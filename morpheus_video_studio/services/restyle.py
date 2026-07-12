# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Video restyle service (视频风格化).

Two tiers, per docs/upgrade-roadmap-2026-07.md §5:

- Filter tier (A 档): ffmpeg filter chains — instant, any length.
- AI repaint tier (B 档): ComfyUI vid2vid — dreamshaper + AnimateDiff for
  temporal coherence, Canny ControlNet to lock structure, LCM-LoRA for
  4-6 step sampling. Fast-path constraints: clips capped at 60s, frames
  processed at ~10fps (native animation cadence), 512p working size.
  The original audio track is muxed back onto the repainted video.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable, Final, Optional

from loguru import logger


# ── Filter tier ──────────────────────────────────────────────────────

FILTER_STYLES: Final[list[dict[str, str]]] = [
    {
        "id": "ghibli_warm",
        "label": "宫崎骏暖调",
        "description": "暖绿色调、柔和高光，手绘动画的温暖气息",
        "vf": (
            "eq=saturation=1.22:brightness=0.03:contrast=1.05,"
            "colorbalance=rm=.05:gm=.03:bm=-.06,"
            "unsharp=5:5:0.5,vignette=angle=PI/5"
        ),
    },
    {
        "id": "film",
        "label": "胶片电影感",
        "description": "复古曲线、细腻颗粒、暗角，院线胶片质感",
        "vf": "curves=preset=vintage,noise=alls=6:allf=t,vignette=angle=PI/4",
    },
    {
        "id": "ink_wash",
        "label": "水墨淡彩",
        "description": "低饱和、高对比、轻柔化，东方水墨意境",
        "vf": "hue=s=0.28,eq=contrast=1.16:brightness=0.05,gblur=sigma=0.4,noise=alls=4:allf=t",
    },
    {
        "id": "cyber_neon",
        "label": "赛博霓虹",
        "description": "高饱和、冷色偏移、锐化，夜之城氛围",
        "vf": "eq=saturation=1.6:contrast=1.18,hue=h=8,unsharp=5:5:0.8,vignette=angle=PI/4",
    },
    {
        "id": "vhs",
        "label": "复古 VHS",
        "description": "色偏、噪点、轻微模糊，90 年代录像带",
        "vf": "chromashift=cbh=3:crh=-3,noise=alls=10:allf=t,eq=saturation=0.85,gblur=sigma=0.35",
    },
    {
        "id": "bw_film",
        "label": "黑白电影",
        "description": "去色、高对比、颗粒与暗角，经典默片味",
        "vf": "hue=s=0,eq=contrast=1.25:brightness=0.03,noise=alls=8:allf=t,vignette=angle=PI/4",
    },
]

AI_RESTYLE_MAX_SECONDS: Final[float] = 60.0
AI_RESTYLE_FPS: Final[int] = 10
AI_RESTYLE_MAX_DIM: Final[int] = 512


def list_filter_styles() -> list[dict[str, str]]:
    return [style.copy() for style in FILTER_STYLES]


def get_filter_style(style_id: str) -> dict[str, str]:
    for style in FILTER_STYLES:
        if style["id"] == style_id:
            return style.copy()
    raise KeyError(f"Unknown filter style: {style_id}")


def probe_video(video_path: str | Path) -> dict[str, Any]:
    """Return duration/width/height/fps for a video file."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(video_path),
        ],
        capture_output=True, text=True, timeout=60,
    )
    data = json.loads(result.stdout or "{}")
    video_stream = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"), {}
    )
    num, _, den = (video_stream.get("r_frame_rate") or "0/1").partition("/")
    fps = (float(num) / float(den)) if den and float(den) else 0.0
    return {
        "duration": float(data.get("format", {}).get("duration") or 0.0),
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
        "fps": fps,
        "has_audio": any(
            s.get("codec_type") == "audio" for s in data.get("streams", [])
        ),
    }


def apply_filter_style(
    video_path: str | Path,
    style_id: str,
    output_path: str | Path,
    preview_seconds: Optional[float] = None,
) -> str:
    """Apply a filter style with ffmpeg; audio is preserved."""
    style = get_filter_style(style_id)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(video_path)]
    if preview_seconds:
        command += ["-t", f"{float(preview_seconds):.2f}"]
    command += [
        "-vf", style["vf"],
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        str(out),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    if completed.returncode != 0:
        raise RuntimeError(f"滤镜处理失败（{style['label']}）：{completed.stderr[-400:]}")
    logger.info(f"🎨 滤镜风格化完成: {style['label']} -> {out}")
    return str(out)


# ── AI repaint tier ──────────────────────────────────────────────────

def build_ai_restyle_graph(
    video_path: str,
    prompt: str,
    *,
    width: int,
    height: int,
    fps: int = AI_RESTYLE_FPS,
    frame_cap: int = 0,
    denoise: float = 0.6,
    controlnet_strength: float = 0.75,
    seed: int = 123456789,
    filename_prefix: str = "morpheus_restyle",
    reference_image: str | None = None,
    reference_strength: float = 0.6,
) -> dict[str, Any]:
    """Build the ComfyUI vid2vid graph (dreamshaper + AD + Lineart CN + LCM).

    reference_image: optional style reference (借鉴 Krea2 edit 的参考图引导思路,
    用 IP-Adapter 轻量落地) — every repainted frame follows the reference's
    style/palette on top of the text prompt.
    """
    negative = (
        "worst quality, low quality, blurry, text, watermark, logo, "
        "deformed, flicker, jpeg artifacts"
    )
    graph = {
        "1": {
            "class_type": "VHS_LoadVideoPath",
            "inputs": {
                "video": video_path,
                "force_rate": float(fps),
                "custom_width": width,
                "custom_height": height,
                "frame_load_cap": frame_cap,
                "skip_first_frames": 0,
                "select_every_nth": 1,
            },
            "_meta": {"title": "Load source video (downsampled)"},
        },
        "2": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "dreamshaper_8.safetensors"},
            "_meta": {"title": "Checkpoint"},
        },
        "3": {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["2", 0],
                "clip": ["2", 1],
                "lora_name": "lcm-lora-sdv15.safetensors",
                "strength_model": 1.0,
                "strength_clip": 1.0,
            },
            "_meta": {"title": "LCM LoRA (4-6 step sampling)"},
        },
        "4": {
            "class_type": "ADE_StandardStaticContextOptions",
            "inputs": {"context_length": 16, "context_overlap": 4},
            "_meta": {"title": "AD context windows (handles >16 frames)"},
        },
        "5": {
            "class_type": "ADE_AnimateDiffLoaderGen1",
            "inputs": {
                "model": ["3", 0],
                "model_name": "v3_sd15_mm.ckpt",
                "beta_schedule": "autoselect",
                "context_options": ["4", 0],
            },
            "_meta": {"title": "AnimateDiff motion module"},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["3", 1], "text": prompt},
            "_meta": {"title": "positive"},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["3", 1], "text": negative},
            "_meta": {"title": "negative"},
        },
        "8": {
            "class_type": "LineArtPreprocessor",
            "inputs": {"image": ["1", 0], "coarse": "disable", "resolution": 512},
            "_meta": {"title": "Line art structure (anime-friendly)"},
        },
        "9": {
            # Advanced loader is mandatory: core ControlNet nodes don't
            # support AnimateDiff's sliding context windows (>16 frames)
            "class_type": "ControlNetLoaderAdvanced",
            "inputs": {"control_net_name": "control_v11p_sd15_lineart_fp16.safetensors"},
            "_meta": {"title": "Lineart ControlNet (Advanced, sliding-context capable)"},
        },
        "10": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": ["6", 0],
                "negative": ["7", 0],
                "control_net": ["9", 0],
                "image": ["8", 0],
                "strength": controlnet_strength,
                "start_percent": 0.0,
                "end_percent": 0.85,
            },
            "_meta": {"title": "Lock structure"},
        },
        "11": {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["1", 0], "vae": ["2", 2]},
            "_meta": {"title": "Source frames to latents"},
        },
        "12": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["5", 0],
                "positive": ["10", 0],
                "negative": ["10", 1],
                "latent_image": ["11", 0],
                "seed": seed,
                "steps": 6,
                "cfg": 1.6,
                "sampler_name": "lcm",
                "scheduler": "sgm_uniform",
                "denoise": denoise,
            },
            "_meta": {"title": "LCM sampling"},
        },
        "13": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["12", 0], "vae": ["2", 2]},
            "_meta": {"title": "Decode"},
        },
        "14": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["13", 0],
                "frame_rate": fps,
                "loop_count": 0,
                "filename_prefix": filename_prefix,
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 19,
                "save_metadata": True,
                "trim_to_audio": False,
                "pingpong": False,
                "save_output": True,
            },
            "_meta": {"title": "Combine"},
        },
    }

    if reference_image:
        graph.update(
            {
                "20": {
                    "class_type": "VHS_LoadImagePath",
                    "inputs": {
                        "image": reference_image,
                        "custom_width": 0,
                        "custom_height": 0,
                    },
                    "_meta": {"title": "Style reference image"},
                },
                "21": {
                    "class_type": "CLIPVisionLoader",
                    "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"},
                    "_meta": {"title": "CLIP vision encoder"},
                },
                "22": {
                    "class_type": "IPAdapterModelLoader",
                    "inputs": {"ipadapter_file": "ip-adapter_sd15.safetensors"},
                    "_meta": {"title": "IP-Adapter"},
                },
                "23": {
                    "class_type": "IPAdapterAdvanced",
                    "inputs": {
                        "model": ["3", 0],
                        "ipadapter": ["22", 0],
                        "image": ["20", 0],
                        "clip_vision": ["21", 0],
                        "weight": reference_strength,
                        "weight_type": "linear",
                        "combine_embeds": "concat",
                        "start_at": 0.0,
                        "end_at": 0.9,
                        "embeds_scaling": "V only",
                    },
                    "_meta": {"title": "Reference-guided repaint (Krea2-edit spirit)"},
                },
            }
        )
        # AnimateDiff consumes the reference-patched model instead of raw LoRA
        graph["5"]["inputs"]["model"] = ["23", 0]

    return graph


def working_size(width: int, height: int, max_dim: int = AI_RESTYLE_MAX_DIM) -> tuple[int, int]:
    """Scale to max_dim on the long side, both dimensions divisible by 8."""
    if width <= 0 or height <= 0:
        return max_dim, max_dim
    scale = min(max_dim / max(width, height), 1.0)
    w = max(int(round(width * scale / 8)) * 8, 64)
    h = max(int(round(height * scale / 8)) * 8, 64)
    return w, h


def run_ai_restyle(
    video_path: str | Path,
    style_prompt: str,
    output_path: str | Path,
    *,
    comfyui_url: str = "http://127.0.0.1:8188",
    comfyui_output_dir: str | Path = Path.home() / "ComfyUI" / "output",
    denoise: float = 0.6,
    seed: Optional[int] = None,
    timeout_seconds: float = 3600.0,
    progress_callback: Optional[Callable[[str], None]] = None,
    reference_image: str | Path | None = None,
    reference_strength: float = 0.6,
) -> str:
    """Repaint a video clip into a new style. Fast-path rules enforced here."""
    source = Path(video_path)
    if not source.exists():
        raise FileNotFoundError(source)
    reference_path: Optional[str] = None
    if reference_image:
        ref = Path(reference_image)
        if not ref.exists():
            raise FileNotFoundError(ref)
        reference_path = str(ref.resolve())

    info = probe_video(source)
    if info["duration"] > AI_RESTYLE_MAX_SECONDS + 0.5:
        raise ValueError(
            f"AI 重绘限 {AI_RESTYLE_MAX_SECONDS:.0f} 秒内的素材（当前 {info['duration']:.0f} 秒）。"
            "长视频请先走风格滤镜，或剪出重点片段再重绘。"
        )

    width, height = working_size(info["width"], info["height"])
    prefix = f"morpheus_restyle_{uuid.uuid4().hex[:8]}"
    graph = build_ai_restyle_graph(
        str(source.resolve()),
        style_prompt,
        width=width,
        height=height,
        denoise=denoise,
        seed=seed if seed is not None else int(time.time()) % 2**31,
        filename_prefix=prefix,
        reference_image=reference_path,
        reference_strength=reference_strength,
    )

    def report(message: str) -> None:
        logger.info(message)
        if progress_callback:
            progress_callback(message)

    report(f"🎬 提交 AI 重绘: {source.name} ({info['duration']:.1f}s → {width}x{height}@{AI_RESTYLE_FPS}fps)")
    request = urllib.request.Request(
        f"{comfyui_url}/prompt",
        data=json.dumps({"prompt": graph, "client_id": uuid.uuid4().hex}).encode(),
        headers={"Content-Type": "application/json"},
    )
    response = json.load(urllib.request.urlopen(request, timeout=30))
    if response.get("node_errors"):
        raise RuntimeError(f"工作流校验失败: {response['node_errors']}")
    prompt_id = response["prompt_id"]

    deadline = time.time() + timeout_seconds
    ai_filename: Optional[str] = None
    while time.time() < deadline:
        time.sleep(5)
        history = json.load(
            urllib.request.urlopen(f"{comfyui_url}/history/{prompt_id}", timeout=15)
        )
        entry = history.get(prompt_id)
        if not entry:
            continue
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            messages = [m for m in status.get("messages", []) if m[0] == "execution_error"]
            detail = messages[-1][1] if messages else status
            raise RuntimeError(f"AI 重绘执行失败: {str(detail)[:400]}")
        if status.get("completed"):
            for output in entry.get("outputs", {}).values():
                for key in ("gifs", "videos"):
                    for item in output.get(key, []):
                        ai_filename = item.get("filename")
            break
    if not ai_filename:
        raise TimeoutError(f"AI 重绘超时（>{timeout_seconds:.0f}s）")

    ai_video = Path(comfyui_output_dir) / ai_filename
    if not ai_video.exists():
        raise FileNotFoundError(f"未找到重绘输出: {ai_video}")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Mux the original narration/music back onto the repainted picture.
    if info["has_audio"]:
        report("🎧 回填原始音轨…")
        completed = subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(ai_video), "-i", str(source),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", str(out),
            ],
            capture_output=True, text=True, timeout=600,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"音轨回填失败: {completed.stderr[-300:]}")
    else:
        out.write_bytes(ai_video.read_bytes())

    report(f"✅ AI 重绘完成: {out}")
    return str(out)
