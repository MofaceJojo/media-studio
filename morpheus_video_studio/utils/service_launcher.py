from __future__ import annotations

import os
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen
from pathlib import Path
from typing import Callable

from morpheus_video_studio.utils.comfyui_util import check_comfyui_health
from morpheus_video_studio.utils.omnivoice_util import check_omnivoice_health


SERVICE_NAMES = ("comfyui", "omnivoice", "web")


def detect_default_service_workdir(service_name: str) -> str:
    home = Path.home()
    candidates: dict[str, list[Path]] = {
        "comfyui": [
            home / "ComfyUI",
            home / "Documents" / "ComfyUI",
        ],
        "omnivoice": [
            home / "OmniVoice-Studio",
            home / "Documents" / "Codex" / "2026-05-17" / "debpalash-omnivoice-studio-git-https-github" / "OmniVoice-Studio",
        ],
        "web": [
            Path.cwd(),
        ],
    }
    for path in candidates.get(service_name, []):
        if path.exists():
            return str(path)
    return ""


def detect_default_service_command(service_name: str, workdir: str) -> str:
    path = Path(workdir).expanduser()
    if service_name == "comfyui":
        if (path / "venv" / "bin" / "python").exists() and (path / "main.py").exists():
            return "./venv/bin/python main.py --listen 127.0.0.1 --port 8188"
        if (path / "main.py").exists():
            return "python main.py --listen 127.0.0.1 --port 8188"
    if service_name == "omnivoice" and (path / "package.json").exists():
        return "bun run dev"
    if service_name == "web" and (path / ".venv" / "bin" / "streamlit").exists() and (path / "web" / "app.py").exists():
        return ".venv/bin/streamlit run web/app.py --server.address 127.0.0.1 --server.port 8501"
    if service_name == "web" and (path / "web" / "app.py").exists():
        return "uv run streamlit run web/app.py --server.address 127.0.0.1 --server.port 8501"
    return ""


def start_local_service(
    service_name: str,
    *,
    workdir: str,
    command: str,
    base_url: str,
    wait_seconds: float = 8.0,
) -> dict[str, str | int | bool]:
    if service_name not in SERVICE_NAMES:
        raise RuntimeError(f"Unsupported service: {service_name}")

    directory = Path(workdir).expanduser()
    if not directory.exists() or not directory.is_dir():
        raise RuntimeError(f"启动目录不存在：{directory}")
    if not command.strip():
        raise RuntimeError("启动命令不能为空。")

    ok, message = _health_check(service_name, base_url)
    if ok:
        return {
            "ok": True,
            "already_running": True,
            "message": message,
            "log_path": "",
            "pid": 0,
        }

    log_dir = Path("output/service_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{service_name}_{timestamp}.log"

    with open(log_path, "ab") as log_file:
        process = subprocess.Popen(
            ["/bin/zsh", "-lc", command],
            cwd=str(directory),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

    deadline = time.time() + wait_seconds
    last_message = message
    while time.time() < deadline:
        time.sleep(1.0)
        ok, last_message = _health_check(service_name, base_url)
        if ok:
            return {
                "ok": True,
                "already_running": False,
                "message": last_message,
                "log_path": str(log_path.resolve()),
                "pid": process.pid,
            }
        if process.poll() is not None:
            break

    if process.poll() is not None:
        tail = _read_log_tail(log_path)
        raise RuntimeError(
            f"{service_name} 启动进程已退出。日志：{log_path.resolve()}\n{tail}".strip()
        )

    return {
        "ok": False,
        "already_running": False,
        "message": f"已发送启动命令，服务可能还在预热中。日志：{log_path.resolve()}",
        "log_path": str(log_path.resolve()),
        "pid": process.pid,
    }


def _health_check(service_name: str, base_url: str) -> tuple[bool, str]:
    if service_name == "comfyui":
        return check_comfyui_health(base_url, timeout=3.0)
    if service_name == "omnivoice":
        return check_omnivoice_health(base_url, timeout=3.0)
    if service_name == "web":
        return check_web_health(base_url, timeout=3.0)
    return False, "未知服务"


def check_web_health(base_url: str, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        with urlopen(base_url, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if 200 <= status < 400:
                return True, f"Media Studio Web 已连接：{base_url}"
            return False, f"Media Studio Web 状态异常：HTTP {status}"
    except URLError as exc:
        return False, f"Media Studio Web 未启动：{exc.reason}"
    except Exception as exc:
        return False, f"Media Studio Web 检查失败：{exc}"


def _read_log_tail(log_path: Path, max_chars: int = 1200) -> str:
    try:
        content = log_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return content[-max_chars:].strip()
