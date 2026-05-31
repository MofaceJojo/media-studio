from __future__ import annotations

from pathlib import Path

import httpx
from pydantic import BaseModel


WORKFLOW_DIR = Path(__file__).resolve().parents[1] / "resources" / "workflows" / "selfhost"


class ComfyConnection(BaseModel):
    base_url: str = "http://127.0.0.1:8188"
    api_key: str = ""


async def test_comfyui(config: ComfyConnection) -> dict:
    headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{config.base_url.rstrip('/')}/system_stats", headers=headers)
            response.raise_for_status()
            data = response.json()
        return {"ok": True, "message": "ComfyUI is reachable.", "system": data}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


def list_selfhost_workflows() -> list[str]:
    if not WORKFLOW_DIR.exists():
        return []
    return sorted(path.name for path in WORKFLOW_DIR.glob("*.json"))
