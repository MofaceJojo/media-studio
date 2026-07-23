"""
Utilities for checking the local HyperFrames renderer.
"""

import shutil
import shlex
import subprocess
from typing import Tuple


def _split_command(command: str) -> list[str]:
    """Split a configured command into argv tokens."""
    return shlex.split(command or "npx --yes hyperframes")


def check_hyperframe_health(command: str = "npx --yes hyperframes", timeout: float = 10.0) -> Tuple[bool, str]:
    """
    Check whether HyperFrames can be invoked locally.

    Returns:
        (ok, message)
    """
    argv = _split_command(command)
    if not argv:
        return False, "HyperFrame command is empty."

    executable = shutil.which(argv[0])
    if executable is None:
        return False, f"HyperFrame command not found: {argv[0]}"

    try:
        result = subprocess.run(
            [*argv, "--help"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"HyperFrame command timed out after {timeout:.0f}s."
    except Exception as exc:
        return False, f"HyperFrame check failed: {exc}"

    output = f"{result.stdout}\n{result.stderr}".lower()
    if result.returncode == 0 and "hyperframes" in output:
        return True, "HyperFrame 可用。"
    if result.returncode == 0:
        return True, "HyperFrame 命令可执行。"

    details = (result.stderr or result.stdout or "").strip()
    if details:
        details = details.splitlines()[-1]
    return False, f"HyperFrame 不可用：{details or 'unknown error'}"
