from __future__ import annotations

import importlib.util
import os
import time
from pathlib import Path
from typing import Any

from loguru import logger

from morpheus_video_studio.config import config_manager


VALID_REPORT_FORMATS = {
    "briefing_doc": "briefing_doc",
    "study_guide": "study_guide",
    "blog_post": "blog_post",
    "custom": "custom",
}


class NotebookLMService:
    """Thin optional adapter around notebooklm-py."""

    def __init__(self, config: dict | None = None):
        self.config = config or config_manager.get_notebooklm_config()

    @staticmethod
    def is_installed() -> bool:
        return importlib.util.find_spec("notebooklm") is not None

    def get_storage_path(self) -> str:
        configured = (self.config.get("auth_json_path") or "").strip()
        if configured:
            return configured
        return os.environ.get("NOTEBOOKLM_AUTH_JSON", "").strip()

    def get_status(self) -> tuple[bool, str]:
        if not self.is_installed():
            return False, "未安装 notebooklm-py，无法启用 NotebookLM Beta。"

        storage_path = self.get_storage_path()
        profile = (self.config.get("profile") or "default").strip()
        if storage_path:
            if not Path(storage_path).expanduser().exists():
                return False, f"NotebookLM 认证文件不存在：{storage_path}"
            return True, f"已检测到认证文件：{storage_path}"

        if profile:
            return True, f"将尝试使用 notebooklm-py 本地 profile：{profile}"

        return False, "缺少 NotebookLM 认证文件或 profile。"

    async def test_connection(self) -> tuple[bool, str]:
        ok, message = self.get_status()
        if not ok:
            return ok, message

        try:
            async with self._open_client():
                return True, "NotebookLM 连接成功。"
        except Exception as exc:
            return False, f"NotebookLM 连接失败：{exc}"

    async def generate_report_from_file(
        self,
        file_path: str | Path,
        title: str,
        output_dir: str | Path,
        extra_instructions: str | None = None,
    ) -> str:
        ok, message = self.get_status()
        if not ok:
            raise RuntimeError(message)

        source_path = Path(file_path).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(source_path)

        output_root = Path(output_dir).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        report_path = output_root / "notebooklm_report.md"
        timeout_seconds = int(self.config.get("timeout_seconds") or 300)
        report_format = VALID_REPORT_FORMATS.get(
            str(self.config.get("report_format") or "study_guide").strip().lower(),
            "study_guide",
        )
        language = (self.config.get("language") or "Chinese").strip() or "Chinese"
        notebook_id: str | None = None

        async with self._open_client() as client:
            try:
                notebook_title = f"{title[:40] or source_path.stem} {int(time.time())}"
                notebook = await client.notebooks.create(notebook_title)
                notebook_id = notebook.id

                await client.sources.add_file(
                    notebook.id,
                    source_path,
                    title=title or source_path.stem,
                    wait=True,
                    wait_timeout=max(timeout_seconds, 120),
                )

                status = await client.artifacts.generate_report(
                    notebook.id,
                    report_format=report_format,
                    language=language,
                    extra_instructions=extra_instructions,
                )
                await client.artifacts.wait_for_completion(
                    notebook.id,
                    status.task_id,
                    timeout=float(timeout_seconds),
                )
                await client.artifacts.download_report(
                    notebook.id,
                    str(report_path),
                    artifact_id=status.task_id,
                )
            finally:
                if notebook_id and self.config.get("auto_cleanup_notebook", True):
                    try:
                        await client.notebooks.delete(notebook_id)
                    except Exception as exc:
                        logger.warning(f"NotebookLM 临时 notebook 清理失败: {exc}")

        if not report_path.exists():
            raise RuntimeError("NotebookLM 报告生成完成，但没有下载到本地文件。")

        return report_path.read_text(encoding="utf-8")

    def _open_client(self) -> Any:
        from notebooklm import NotebookLMClient

        timeout_seconds = float(self.config.get("timeout_seconds") or 300)
        storage_path = self.get_storage_path()
        profile = (self.config.get("profile") or "default").strip() or "default"
        kwargs: dict[str, Any] = {
            "timeout": min(timeout_seconds, 60.0),
            "chat_timeout": timeout_seconds,
            "server_error_max_retries": 1,
            "rate_limit_max_retries": 1,
        }
        if storage_path:
            kwargs["path"] = str(Path(storage_path).expanduser())
        else:
            kwargs["profile"] = profile
        return NotebookLMClient.from_storage(**kwargs)
