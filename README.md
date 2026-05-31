# Morpheus Video Studio

Morpheus Video Studio is a consolidated short-video workspace inspired by MoneyPrinterPlus, MoneyPrinterTurbo v1.2.8, and Pixelle-Video.

This first integrated build keeps the free/local-first pieces:

- Pexels and Pixabay online material search, using a MoneyPrinterTurbo-style key rotation and TLS-safe request flow.
- Local/self-hosted ComfyUI workflows copied from Pixelle-Video `workflows/selfhost`.
- Local/free voice options only: Edge TTS, ComfyUI TTS workflows, and a generic Local Voice API for Omni Voice-style engines.
- OpenAI-compatible LLM providers with presets, default Base URLs, model fetching, custom model entry, and one-click connection tests.
- No RunningHub cloud configuration or workflow surface.

## Run

Quick start:

```bash
./install.sh
./run.sh
```

Open `http://localhost:5173`.

Requirements:

- Python 3.12 recommended
- Node.js 20+
- ffmpeg available on PATH

Backend:

```bash
cd backend
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8710
```

Python 3.12 is recommended on macOS right now. Python 3.14 can force source builds for some packages.

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Local Generation

The app can generate a basic MP4 without API keys:

1. Open `Local Video Generator`.
2. Enter a title and topic, or paste a script.
3. Pick `Edge TTS`, `Local Voice API`, or `None` for voiceover.
4. Keep `Burn captions into video` enabled if you want readable subtitles.
5. Optionally paste local image or video paths, one per line, to use them as scene backgrounds.
6. Click `Generate MP4`.
7. The generated video is saved under `backend/storage/generated` and served from `/outputs/.../final.mp4`.

The first generation path is intentionally simple: text scenes are rendered to image/video scene clips and combined with ffmpeg. Morpheus can cycle local image and video files as backgrounds, writes a standard `subtitles.srt` file, and can burn captions into the video frames. When Edge TTS is reachable, Morpheus generates a real voiceover and stretches scene duration to fit the audio. If voice generation fails, it falls back to a silent AAC track so video generation still completes.

For Omni Voice-style local engines, choose `Local Voice API`. Morpheus sends:

```http
POST /tts
Content-Type: application/json

{"text":"...", "voice":"..."}
```

The endpoint should return audio bytes. Pexels, Pixabay, ComfyUI, and LLM providers remain available as integration points.

## Writing Tools

`Novel & Polish Lab` includes local tools for:

- turning rough prose into a short-video script
- polishing text
- creating a compact novel outline

## Integration Notes

The product blueprint follows MoneyPrinterPlus because it has the broadest workflow coverage: generation, mixing, publishing-oriented screens, local TTS, and resource providers.

MoneyPrinterTurbo v1.2.8 is stronger for stock-video retrieval and final video assembly robustness, especially around Pexels/Pixabay key rotation, TLS verification, media validation, and task-oriented API structure. Morpheus uses that approach for the material adapter.

Pixelle-Video is strongest for modern local ComfyUI AI-video workflows and structured pipeline design. Morpheus imports only self-hosted workflow assets and exposes them as local options.

## License Notice

This repository includes license copies for the upstream projects in `docs/`. MoneyPrinterPlus contains non-commercial restrictions in its license text, so publish this repository privately unless you have permission for public/commercial redistribution.
