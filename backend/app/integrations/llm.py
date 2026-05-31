from __future__ import annotations

import httpx
from pydantic import BaseModel, Field

from app.core.provider_presets import PROVIDER_PRESETS


class LLMConnection(BaseModel):
    provider: str = "openai"
    api_key: str = ""
    base_url: str = ""
    model: str = ""


class TestResult(BaseModel):
    ok: bool
    message: str
    models: list[str] = Field(default_factory=list)


def resolve_connection(config: LLMConnection) -> LLMConnection:
    preset = PROVIDER_PRESETS.get(config.provider, PROVIDER_PRESETS["custom"])
    base_url = config.base_url.strip() or preset.base_url
    model = config.model.strip() or preset.default_model
    return LLMConnection(
        provider=config.provider,
        api_key=config.api_key.strip(),
        base_url=base_url.rstrip("/"),
        model=model,
    )


async def fetch_models(config: LLMConnection) -> list[str]:
    resolved = resolve_connection(config)
    preset = PROVIDER_PRESETS.get(resolved.provider, PROVIDER_PRESETS["custom"])
    if not resolved.base_url:
        return preset.fallback_models

    headers = {"Authorization": f"Bearer {resolved.api_key}"} if resolved.api_key else {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{resolved.base_url}/models", headers=headers)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return preset.fallback_models

    raw_models = data.get("data", []) if isinstance(data, dict) else []
    models = sorted(
        model.get("id", "")
        for model in raw_models
        if isinstance(model, dict) and model.get("id")
    )
    return models or preset.fallback_models


async def test_llm(config: LLMConnection) -> TestResult:
    resolved = resolve_connection(config)
    preset = PROVIDER_PRESETS.get(resolved.provider, PROVIDER_PRESETS["custom"])
    if preset.requires_api_key and not resolved.api_key:
        return TestResult(ok=False, message="API key is required.")
    if not resolved.base_url:
        return TestResult(ok=False, message="Base URL is required.")

    models = await fetch_models(resolved)
    if resolved.provider == "ollama":
        return TestResult(ok=bool(models), message="Ollama endpoint reachable.", models=models)
    if models:
        return TestResult(ok=True, message=f"Connection OK. {len(models)} models available.", models=models)
    return TestResult(ok=False, message="Connection failed or no models returned.")
