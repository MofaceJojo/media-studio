"""
Lightweight content/audio asset persistence for Media Studio.
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger


class StudioLibraryService:
    """Filesystem-backed content and audio asset library."""

    def __init__(self, base_dir: str = "data/studio"):
        self.base_dir = Path(base_dir)
        self.content_dir = self.base_dir / "content"
        self.audio_dir = self.base_dir / "audio"
        self.content_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def list_content_items(self) -> list[dict[str, Any]]:
        items = [self._read_json(path) for path in self.content_dir.glob("*/metadata.json")]
        return sorted(
            [item for item in items if item],
            key=lambda item: item.get("updated_at") or item.get("created_at") or "",
            reverse=True,
        )

    def get_content_item(self, content_id: str) -> Optional[dict[str, Any]]:
        path = self.content_dir / content_id / "metadata.json"
        return self._read_json(path) if path.exists() else None

    def create_text_item(
        self,
        title: str,
        text: str,
        content_type: str,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        content_id = f"content_{uuid.uuid4().hex[:12]}"
        item_dir = self.content_dir / content_id
        item_dir.mkdir(parents=True, exist_ok=True)

        extracted_path = item_dir / "extracted.txt"
        extracted_path.write_text(text, encoding="utf-8")
        now = self._now()
        metadata = {
            "content_id": content_id,
            "title": title.strip() or content_id,
            "content_type": content_type,
            "source_kind": "text",
            "source_path": None,
            "source_filename": None,
            "extracted_text_path": str(extracted_path.resolve()),
            "char_count": len(text),
            "summary": self._build_summary(text),
            "tags": tags or [],
            "status": "ready",
            "created_at": now,
            "updated_at": now,
        }
        self._write_json(item_dir / "metadata.json", metadata)
        return metadata

    def import_document(
        self,
        source_path: str | Path,
        extracted_text: str,
        content_type: str,
        title: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(source)

        content_id = f"content_{uuid.uuid4().hex[:12]}"
        item_dir = self.content_dir / content_id
        item_dir.mkdir(parents=True, exist_ok=True)

        stored_source = item_dir / source.name
        shutil.copy2(source, stored_source)
        extracted_path = item_dir / "extracted.txt"
        extracted_path.write_text(extracted_text, encoding="utf-8")

        now = self._now()
        metadata = {
            "content_id": content_id,
            "title": (title or source.stem).strip() or content_id,
            "content_type": content_type,
            "source_kind": "document",
            "source_path": str(stored_source.resolve()),
            "source_filename": source.name,
            "extracted_text_path": str(extracted_path.resolve()),
            "char_count": len(extracted_text),
            "summary": self._build_summary(extracted_text),
            "tags": tags or [],
            "status": "ready",
            "created_at": now,
            "updated_at": now,
        }
        self._write_json(item_dir / "metadata.json", metadata)
        return metadata

    def list_audio_assets(self) -> list[dict[str, Any]]:
        items = [self._read_json(path) for path in self.audio_dir.glob("*/metadata.json")]
        return sorted(
            [item for item in items if item],
            key=lambda item: item.get("created_at") or "",
            reverse=True,
        )

    def list_video_assets(self) -> list[dict[str, Any]]:
        index_path = Path("output/.index.json")
        if not index_path.exists():
            return []

        index = self._read_json(index_path) or {}
        tasks = index.get("tasks", [])
        assets: list[dict[str, Any]] = []

        for task in tasks:
            video_path = task.get("video_path")
            task_id = task.get("task_id")
            if not video_path or not task_id:
                continue
            video_file = Path(video_path)
            if not video_file.exists():
                continue

            metadata = self._read_json(Path("output") / task_id / "metadata.json") or {}
            input_data = metadata.get("input", {})
            assets.append(
                {
                    "asset_id": task_id,
                    "title": task.get("title") or task_id,
                    "video_path": str(video_file.resolve()),
                    "status": task.get("status"),
                    "duration": task.get("duration"),
                    "file_size": task.get("file_size"),
                    "n_frames": task.get("n_frames"),
                    "created_at": task.get("created_at"),
                    "completed_at": task.get("completed_at"),
                    "source_text_preview": self._build_summary(input_data.get("text") or ""),
                    "mode": input_data.get("mode"),
                    "pipeline": metadata.get("pipeline") or input_data.get("pipeline"),
                }
            )

        return sorted(
            assets,
            key=lambda item: item.get("created_at") or "",
            reverse=True,
        )

    def save_audio_asset(
        self,
        audio_path: str | Path,
        title: str,
        engine: str,
        voice: Optional[str],
        speed: Optional[float],
        content_id: Optional[str] = None,
        source_text: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        source = Path(audio_path)
        if not source.exists():
            raise FileNotFoundError(source)

        asset_id = f"audio_{uuid.uuid4().hex[:12]}"
        asset_dir = self.audio_dir / asset_id
        asset_dir.mkdir(parents=True, exist_ok=True)

        stored_audio = asset_dir / f"asset{source.suffix.lower() or '.mp3'}"
        shutil.copy2(source, stored_audio)

        now = self._now()
        metadata = {
            "asset_id": asset_id,
            "title": title.strip() or asset_id,
            "engine": engine,
            "voice": voice,
            "speed": speed,
            "content_id": content_id,
            "source_text_preview": self._build_summary(source_text or ""),
            "audio_path": str(stored_audio.resolve()),
            "duration_seconds": self._probe_duration(stored_audio),
            "tags": tags or [],
            "created_at": now,
        }
        self._write_json(asset_dir / "metadata.json", metadata)
        return metadata

    def _probe_duration(self, audio_path: Path) -> Optional[float]:
        try:
            import ffmpeg

            probe = ffmpeg.probe(str(audio_path))
            return round(float(probe["format"]["duration"]), 3)
        except Exception as exc:
            logger.debug(f"Failed to probe audio duration for {audio_path}: {exc}")
            return None

    def _build_summary(self, text: str, limit: int = 160) -> str:
        normalized = " ".join((text or "").split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 1].rstrip() + "…"

    def _read_json(self, path: Path) -> Optional[dict[str, Any]]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Failed to read studio metadata {path}: {exc}")
            return None

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _now(self) -> str:
        return datetime.now().isoformat()
