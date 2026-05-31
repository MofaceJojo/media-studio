from __future__ import annotations

from pydantic import BaseModel


class ProviderPreset(BaseModel):
    id: str
    name: str
    base_url: str
    default_model: str
    api_key_url: str | None = None
    requires_api_key: bool = True
    fallback_models: list[str]


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset(
        id="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        api_key_url="https://platform.openai.com/api-keys",
        fallback_models=["gpt-4o", "gpt-4o-mini", "gpt-4.1-mini"],
    ),
    "openrouter": ProviderPreset(
        id="openrouter",
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-4o-mini",
        api_key_url="https://openrouter.ai/keys",
        fallback_models=[
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.5-flash",
            "deepseek/deepseek-chat",
            "meta-llama/llama-3.3-70b-instruct",
        ],
    ),
    "deepseek": ProviderPreset(
        id="deepseek",
        name="DeepSeek",
        base_url="https://api.deepseek.com",
        default_model="deepseek-chat",
        api_key_url="https://platform.deepseek.com/api_keys",
        fallback_models=["deepseek-chat", "deepseek-reasoner"],
    ),
    "qwen": ProviderPreset(
        id="qwen",
        name="Qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-max",
        api_key_url="https://dashscope.console.aliyun.com/apiKey",
        fallback_models=["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],
    ),
    "moonshot": ProviderPreset(
        id="moonshot",
        name="Moonshot",
        base_url="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-8k",
        api_key_url="https://platform.moonshot.cn/console/api-keys",
        fallback_models=["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    ),
    "ollama": ProviderPreset(
        id="ollama",
        name="Ollama",
        base_url="http://127.0.0.1:11434/v1",
        default_model="llama3.2",
        requires_api_key=False,
        fallback_models=["llama3.2", "qwen2.5", "mistral", "gemma2"],
    ),
    "minimax": ProviderPreset(
        id="minimax",
        name="MiniMax",
        base_url="https://api.minimax.io/v1",
        default_model="MiniMax-M2.7",
        api_key_url="https://platform.minimax.io",
        fallback_models=["MiniMax-M2.7", "MiniMax-M2.7-highspeed"],
    ),
    "xai": ProviderPreset(
        id="xai",
        name="xAI",
        base_url="https://api.x.ai/v1",
        default_model="grok-4.3",
        api_key_url="https://console.x.ai",
        fallback_models=["grok-4.3", "grok-4-fast"],
    ),
    "modelscope": ProviderPreset(
        id="modelscope",
        name="ModelScope",
        base_url="https://api-inference.modelscope.cn/v1",
        default_model="Qwen/Qwen3-32B",
        api_key_url="https://modelscope.cn/docs/model-service/API-Inference/intro",
        fallback_models=["Qwen/Qwen3-32B", "Qwen/Qwen3-Coder-30B-A3B-Instruct"],
    ),
    "custom": ProviderPreset(
        id="custom",
        name="Custom OpenAI-compatible",
        base_url="",
        default_model="",
        fallback_models=[],
    ),
}


def presets_payload() -> list[dict]:
    return [preset.model_dump() for preset in PROVIDER_PRESETS.values()]
