# Integration Assessment

## Base Project

MoneyPrinterPlus is the best product blueprint because it already includes generation, mixing, publishing-oriented pages, local TTS options, resource providers, subtitles, and a broad configuration surface.

## Video Model Decision

MoneyPrinterTurbo v1.2.8 is better than MoneyPrinterPlus for the stock-video path. Its material service has key rotation, explicit TLS verification, better timeout handling, and tests around Pexels/Pixabay behavior. Morpheus therefore adopts this approach for online video material search.

For AI-generated video, Pixelle-Video is stronger than both because it has current self-hosted ComfyUI workflows for image/video/TTS and a cleaner pipeline split. Morpheus keeps Pixelle self-host workflows and removes RunningHub workflows.

## Removed

- RunningHub cloud settings and workflows.
- Paid cloud TTS providers from the active UI: Azure, AliCloud, and Tencent Cloud.
- Recommendation-style helper copy. Configuration notes are behind small question buttons.

## Kept

- Pexels API and Pixabay API.
- Free/local TTS: Edge TTS, ChatTTS, GPT-SoVITS, CosyVoice, ComfyUI TTS.
- Local ComfyUI.
- OpenAI-compatible LLM providers with OpenRouter, fallback model lists, model loading, and one-click tests.
