# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Helpers for OmniVoice OpenAI-compatible local API."""

from __future__ import annotations

import re
from typing import Any, Optional, Tuple

import httpx

# OmniVoice rejects free-form English sentences and emotion words like「深情」.
_INVALID_INSTRUCT_SNIPPETS = (
    "warm natural narration",
    "speak with",
    "bedtime story",
    "dramatic flair",
)
_DEFAULT_INSTRUCT_ZH = "男，青年"


def normalize_omnivoice_instruct(instruct: Optional[str]) -> Optional[str]:
    """Return a safe instruct string for OmniVoice, or None to omit the field."""
    if instruct is None:
        return None
    text = instruct.strip()
    if not text:
        return None
    lower = text.lower()
    if any(snippet in lower for snippet in _INVALID_INSTRUCT_SNIPPETS):
        return _DEFAULT_INSTRUCT_ZH
    # Long free-form English prose is almost always rejected by OmniVoice.
    if len(text) > 40 and re.search(r"[a-zA-Z]{4,}", text) and "，" not in text and "," not in text:
        return _DEFAULT_INSTRUCT_ZH
    return text


def check_omnivoice_health(base_url: str, timeout: float = 3.0) -> Tuple[bool, str]:
    """Ping OmniVoice /v1/audio/voices. Returns (ok, message)."""
    url = base_url.rstrip("/")
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.get(f"{url}/v1/audio/voices")
            response.raise_for_status()
            payload = response.json()
            count = len(payload.get("voices", []))
            return True, f"OmniVoice 已连接（{count} 个音色）"
    except httpx.ConnectError:
        return False, "无法连接 OmniVoice：请先启动 OmniVoice Studio（端口 3900）"
    except httpx.HTTPStatusError as exc:
        return False, f"OmniVoice 返回 HTTP {exc.response.status_code}"
    except Exception as exc:
        return False, f"OmniVoice 检测失败: {exc}"


def fetch_omnivoice_catalog(base_url: str, timeout: float = 3.0) -> dict[str, list[dict[str, Any]]]:
    """Fetch available voices and engines from OmniVoice Studio."""
    url = base_url.rstrip("/")
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        response = client.get(f"{url}/v1/audio/voices")
        response.raise_for_status()
        payload = response.json()
    return {
        "voices": payload.get("voices", []) or [],
        "engines": payload.get("engines", []) or [],
    }


def fetch_omnivoice_profiles(base_url: str, timeout: float = 3.0) -> list[dict[str, Any]]:
    """Fetch saved voice profiles from OmniVoice Studio."""
    url = base_url.rstrip("/")
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        response = client.get(f"{url}/profiles")
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, list) else []


def fetch_omnivoice_model_status(base_url: str, timeout: float = 3.0) -> dict[str, Any]:
    """Fetch current model loading status from OmniVoice Studio."""
    url = base_url.rstrip("/")
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        response = client.get(f"{url}/model/status")
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, dict) else {}


def build_omnivoice_profile_audio_url(base_url: str, profile_id: str) -> str:
    """Return the preview URL for a voice profile's reference audio."""
    return f"{base_url.rstrip('/')}/profiles/{profile_id}/audio"


def create_omnivoice_profile(
    base_url: str,
    *,
    name: str,
    filename: str,
    content: bytes,
    ref_text: str = "",
    instruct: str = "",
    language: str = "Auto",
    personality: str = "",
    seed: Optional[int] = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Create a new voice profile from uploaded reference audio."""
    url = base_url.rstrip("/")
    data: dict[str, Any] = {
        "name": name,
        "ref_text": ref_text,
        "instruct": instruct,
        "language": language,
        "personality": personality,
    }
    if seed is not None:
        data["seed"] = str(seed)
    files = {"ref_audio": (filename, content, "application/octet-stream")}
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        response = client.post(f"{url}/profiles", data=data, files=files)
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, dict) else {}


def delete_omnivoice_profile(base_url: str, profile_id: str, timeout: float = 20.0) -> None:
    """Delete a voice profile from OmniVoice Studio."""
    url = base_url.rstrip("/")
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        response = client.delete(f"{url}/profiles/{profile_id}")
        response.raise_for_status()


def create_omnivoice_transcription(
    base_url: str,
    *,
    filename: str,
    content: bytes,
    model: str = "whisper-1",
    language: Optional[str] = None,
    prompt: Optional[str] = None,
    response_format: str = "verbose_json",
    timeout: float = 180.0,
) -> dict[str, Any] | str:
    """Send an audio or video file to OmniVoice's transcription endpoint."""
    url = base_url.rstrip("/")
    data: dict[str, Any] = {
        "model": model,
        "response_format": response_format,
    }
    if language:
        data["language"] = language
    if prompt:
        data["prompt"] = prompt
    files = {"file": (filename, content, "application/octet-stream")}
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        response = client.post(f"{url}/v1/audio/transcriptions", data=data, files=files)
        response.raise_for_status()
        if response_format in {"json", "verbose_json"}:
            payload = response.json()
            return payload if isinstance(payload, dict) else {}
        return response.text


def generate_omnivoice_openai_speech(
    base_url: str,
    *,
    text: str,
    model: str = "omnivoice",
    voice: str = "default",
    response_format: str = "mp3",
    speed: float = 1.0,
    language: Optional[str] = None,
    instruct: Optional[str] = None,
    duration: Optional[float] = None,
    seed: Optional[int] = None,
    timeout: float = 900.0,
) -> dict[str, Any]:
    """Call OmniVoice's OpenAI-compatible speech endpoint."""
    url = base_url.rstrip("/")
    payload: dict[str, Any] = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": response_format,
        "speed": speed,
    }
    if language and language != "Auto":
        payload["language"] = language
    safe_instruct = normalize_omnivoice_instruct(instruct)
    if safe_instruct:
        payload["instruct"] = safe_instruct
    if duration is not None:
        payload["duration"] = duration
    if seed is not None:
        payload["seed"] = seed

    request_timeout = httpx.Timeout(connect=10.0, read=timeout, write=120.0, pool=120.0)
    with httpx.Client(timeout=request_timeout, trust_env=False) as client:
        response = client.post(f"{url}/v1/audio/speech", json=payload)
        response.raise_for_status()
        return {
            "audio_bytes": response.content,
            "media_type": response.headers.get("content-type", "audio/mpeg"),
        }


def generate_omnivoice_audio(
    base_url: str,
    *,
    text: str,
    language: Optional[str] = None,
    filename: Optional[str] = None,
    ref_audio_content: Optional[bytes] = None,
    ref_text: Optional[str] = None,
    instruct: Optional[str] = None,
    duration: Optional[float] = None,
    num_step: int = 16,
    guidance_scale: float = 2.0,
    speed: float = 1.0,
    denoise: bool = True,
    postprocess_output: bool = True,
    layer_penalty_factor: Optional[float] = None,
    position_temperature: Optional[float] = None,
    class_temperature: Optional[float] = None,
    profile_id: Optional[str] = None,
    seed: Optional[int] = None,
    timeout: float = 900.0,
) -> dict[str, Any]:
    """Call OmniVoice native /generate endpoint and return WAV bytes plus metadata headers."""
    url = base_url.rstrip("/")
    data: dict[str, Any] = {
        "text": text,
        "num_step": str(num_step),
        "guidance_scale": str(guidance_scale),
        "speed": str(speed),
        "denoise": str(denoise).lower(),
        "postprocess_output": str(postprocess_output).lower(),
    }
    if language and language != "Auto":
        data["language"] = language
    if ref_text:
        data["ref_text"] = ref_text
    safe_instruct = normalize_omnivoice_instruct(instruct)
    if safe_instruct:
        data["instruct"] = safe_instruct
    if duration is not None:
        data["duration"] = str(duration)
    if layer_penalty_factor is not None:
        data["layer_penalty_factor"] = str(layer_penalty_factor)
    if position_temperature is not None:
        data["position_temperature"] = str(position_temperature)
    if class_temperature is not None:
        data["class_temperature"] = str(class_temperature)
    if profile_id:
        data["profile_id"] = profile_id
    if seed is not None:
        data["seed"] = str(seed)

    files = None
    if ref_audio_content is not None:
        files = {
            "ref_audio": (
                filename or "reference.wav",
                ref_audio_content,
                "application/octet-stream",
            )
        }

    request_timeout = httpx.Timeout(connect=10.0, read=timeout, write=120.0, pool=120.0)
    with httpx.Client(timeout=request_timeout, trust_env=False) as client:
        response = client.post(f"{url}/generate", data=data, files=files)
        response.raise_for_status()
        return {
            "audio_bytes": response.content,
            "audio_id": response.headers.get("X-Audio-Id"),
            "generation_time": response.headers.get("X-Gen-Time"),
            "audio_duration": response.headers.get("X-Audio-Duration"),
            "audio_path": response.headers.get("X-Audio-Path"),
            "seed": response.headers.get("X-Seed"),
            "media_type": response.headers.get("content-type", "audio/wav"),
        }


def format_omnivoice_error(
    exc: Exception,
    *,
    model_status: Optional[dict[str, Any]] = None,
    timeout_seconds: Optional[float] = None,
) -> str:
    """Turn httpx/API errors into actionable UI messages."""
    if isinstance(exc, httpx.HTTPStatusError):
        detail = ""
        try:
            body = exc.response.json()
            detail = body.get("detail", "")
            if isinstance(detail, list):
                detail = "; ".join(str(item) for item in detail[:3])
        except Exception:
            detail = exc.response.text[:300]
        if exc.response.status_code == 502 and model_status:
            detail_text = (model_status.get("detail") or model_status.get("sub_stage") or "").strip()
            if bool(model_status.get("loading")) and not bool(model_status.get("loaded")):
                if detail_text == "Model ready":
                    return (
                        "OmniVoice 后端返回 502：模型显示 `Model ready`，但实际仍卡在 loading。"
                        "这不是 Media Studio 的脚本问题，请先重启 OmniVoice Studio，再重试。"
                    )
                return (
                    f"OmniVoice 后端返回 502：模型仍在加载中（{detail_text or 'loading'}）。"
                    "请等待模型完成预热，或重启 OmniVoice Studio 后再试。"
                )
        if detail:
            if "Unsupported instruct" in str(detail) or "unsupported" in str(detail).lower():
                return (
                    f"OmniVoice 风格指令无效：{detail}\n"
                    "请改用预设标签，例如：男，青年 或 male, young adult（不要写长段英文描述）。"
                )
            return f"OmniVoice 合成失败 (HTTP {exc.response.status_code}): {detail}"
        return f"OmniVoice 合成失败 (HTTP {exc.response.status_code})"
    if isinstance(exc, httpx.ConnectError):
        return "无法连接 OmniVoice Studio，请确认应用已启动且 http://127.0.0.1:3900 可访问。"
    if isinstance(exc, httpx.TimeoutException):
        waited = f"{timeout_seconds:.0f}s" if timeout_seconds else "较长时间"
        if model_status:
            status = model_status.get("status")
            loaded = bool(model_status.get("loaded"))
            loading = bool(model_status.get("loading"))
            detail = (model_status.get("detail") or model_status.get("sub_stage") or "").strip()
            progress = model_status.get("progress")
            progress_text = f"（{progress}%）" if progress is not None else ""

            if loading and detail == "Model ready" and not loaded:
                return (
                    f"OmniVoice 响应超时：本次已等待 {waited}。"
                    "后端状态异常，模型显示 `Model ready` 但仍停留在 loading。"
                    "请先重启 OmniVoice Studio，再重试。"
                )
            if status == "loading" or loading:
                suffix = f"当前阶段：{detail}{progress_text}。" if detail else ""
                return (
                    f"OmniVoice 响应超时：本次已等待 {waited}。"
                    f"{suffix}首次下载或编译模型可能需要数分钟，请稍后重试。"
                )
            if status == "idle":
                return (
                    f"OmniVoice 响应超时：本次已等待 {waited}。"
                    "模型还未完成预热；首次启动会先加载本地模型。"
                    "如果多次出现，请打开 OmniVoice Studio 检查模型状态。"
                )
            if status == "ready" or loaded:
                return (
                    f"OmniVoice 响应超时：本次已等待 {waited}。"
                    "模型虽然已就绪，但这次生成没有正常返回，后端可能卡住了。"
                    "建议重启 OmniVoice Studio 后再试。"
                )
        return f"OmniVoice 响应超时：本次已等待 {waited}，请稍后重试。"
    return str(exc)
