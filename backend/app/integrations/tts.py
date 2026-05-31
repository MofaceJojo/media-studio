from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
from pydantic import BaseModel


LOCAL_TTS_PROVIDERS = [
    {
        "id": "edge",
        "name": "Edge TTS",
        "kind": "free-online",
        "requiresApiKey": False,
    },
    {
        "id": "comfyui",
        "name": "ComfyUI TTS workflow",
        "kind": "selfhost-workflow",
        "requiresApiKey": False,
    },
    {
        "id": "local_api",
        "name": "Local Voice API",
        "kind": "local-http",
        "requiresApiKey": False,
        "defaultUrl": "http://127.0.0.1:9880",
    },
]


class TTSPreviewRequest(BaseModel):
    provider: str = "edge"
    text: str = "Morpheus Video Studio voice test."
    voice: str = "zh-CN-XiaoxiaoNeural"
    base_url: str = ""


async def test_tts(payload: TTSPreviewRequest) -> dict:
    if payload.provider == "comfyui":
        return {
            "ok": True,
            "message": "ComfyUI TTS selected. Use the ComfyUI connection test and a self-hosted TTS workflow.",
        }

    if payload.provider == "local_api":
        base_url = payload.base_url.strip().rstrip("/")
        if not base_url:
            return {"ok": False, "message": "Local Voice API URL is required."}
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{base_url}/health")
                if response.status_code == 404:
                    response = await client.get(base_url)
                response.raise_for_status()
            return {"ok": True, "message": "Local Voice API is reachable."}
        except Exception as exc:
            return {"ok": False, "message": f"Local Voice API test failed: {exc}"}

    try:
        import edge_tts

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "preview.mp3"
            communicate = edge_tts.Communicate(payload.text, payload.voice)
            await communicate.save(str(output))
            return {"ok": output.exists() and output.stat().st_size > 0, "message": "Edge TTS preview generated."}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
