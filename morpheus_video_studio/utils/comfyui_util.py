# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Helpers for local ComfyUI connectivity checks."""

from __future__ import annotations

from typing import Tuple

import httpx


def check_comfyui_health(comfyui_url: str, timeout: float = 5.0) -> Tuple[bool, str]:
    """Ping ComfyUI /system_stats. Returns (ok, message)."""
    base = comfyui_url.rstrip("/")
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            response = client.get(f"{base}/system_stats")
            response.raise_for_status()
            return True, f"ComfyUI 已连接：{base}"
    except httpx.ConnectError:
        return (
            False,
            f"无法连接 ComfyUI（{base}）。请先运行 ComfyUI/start_comfyui.command 并打开该地址。",
        )
    except httpx.HTTPStatusError as exc:
        return False, f"ComfyUI 返回 HTTP {exc.response.status_code}"
    except Exception as exc:
        return False, f"ComfyUI 检测失败: {exc}"
