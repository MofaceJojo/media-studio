# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Helpers for OmniVoice OpenAI-compatible local API."""

from __future__ import annotations

import re
from typing import Optional, Tuple

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


def format_omnivoice_error(exc: Exception) -> str:
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
        return "OmniVoice 响应超时：首次加载模型可能需要 30–60 秒，请稍后重试。"
    return str(exc)
