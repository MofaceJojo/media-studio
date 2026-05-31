from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.provider_presets import presets_payload
from app.integrations.comfyui import ComfyConnection, list_selfhost_workflows, test_comfyui
from app.integrations.llm import LLMConnection, fetch_models, test_llm
from app.integrations.materials import MaterialSearchRequest, search_materials
from app.integrations.tts import LOCAL_TTS_PROVIDERS, TTSPreviewRequest, test_tts
from app.integrations.video_generator import STORAGE_DIR, VideoGenerateRequest, generate_local_video
from app.integrations.writing import WritingRequest, run_writing_tool


app = FastAPI(title="Morpheus Video Studio API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STORAGE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(STORAGE_DIR)), name="outputs")


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "name": "Morpheus Video Studio"}


@app.get("/api/llm/providers")
async def llm_providers() -> list[dict]:
    return presets_payload()


@app.post("/api/llm/models")
async def llm_models(payload: LLMConnection) -> dict:
    return {"models": await fetch_models(payload)}


@app.post("/api/llm/test")
async def llm_test(payload: LLMConnection) -> dict:
    return (await test_llm(payload)).model_dump()


@app.post("/api/materials/test")
async def materials_test(payload: MaterialSearchRequest) -> dict:
    return (await search_materials(payload)).model_dump()


@app.post("/api/comfyui/test")
async def comfyui_test(payload: ComfyConnection) -> dict:
    return await test_comfyui(payload)


@app.get("/api/comfyui/workflows")
async def comfyui_workflows() -> dict:
    return {"selfhost": list_selfhost_workflows()}


@app.get("/api/tts/providers")
async def tts_providers() -> dict:
    return {"providers": LOCAL_TTS_PROVIDERS}


@app.post("/api/tts/test")
async def tts_test(payload: TTSPreviewRequest) -> dict:
    return await test_tts(payload)


@app.post("/api/writing/run")
async def writing_run(payload: WritingRequest) -> dict:
    return run_writing_tool(payload).model_dump()


@app.post("/api/video/generate")
async def video_generate(payload: VideoGenerateRequest) -> dict:
    return generate_local_video(payload).model_dump()
