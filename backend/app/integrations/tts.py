from __future__ import annotations

import tempfile
from pathlib import Path

from pydantic import BaseModel


LOCAL_TTS_PROVIDERS = [
    {"id": "edge", "name": "Edge TTS", "kind": "free-online", "requiresApiKey": False},
    {"id": "chattts", "name": "ChatTTS", "kind": "local-server", "requiresApiKey": False, "defaultUrl": "http://127.0.0.1:8080"},
    {"id": "gptsovits", "name": "GPT-SoVITS", "kind": "local-server", "requiresApiKey": False, "defaultUrl": "http://127.0.0.1:9880"},
    {"id": "cosyvoice", "name": "CosyVoice", "kind": "local-server", "requiresApiKey": False, "defaultUrl": "http://127.0.0.1:50000"},
    {"id": "comfyui", "name": "ComfyUI TTS workflow", "kind": "selfhost-workflow", "requiresApiKey": False},
]


class TTSPreviewRequest(BaseModel):
    provider: str = "edge"
    text: str = "Morpheus Video Studio voice test."
    voice: str = "zh-CN-XiaoxiaoNeural"


async def test_tts(payload: TTSPreviewRequest) -> dict:
    if payload.provider != "edge":
        return {"ok": True, "message": "Local provider selected. Start its local server and use preview in the generation flow."}
    try:
        import edge_tts

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "preview.mp3"
            communicate = edge_tts.Communicate(payload.text, payload.voice)
            await communicate.save(str(output))
            return {"ok": output.exists() and output.stat().st_size > 0, "message": "Edge TTS preview generated."}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
