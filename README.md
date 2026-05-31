# Morpheus Video Studio

Morpheus Video Studio is a consolidated short-video workspace inspired by MoneyPrinterPlus, MoneyPrinterTurbo v1.2.8, and Pixelle-Video.

This first integrated build keeps the free/local-first pieces:

- Pexels and Pixabay online material search, using a MoneyPrinterTurbo-style key rotation and TLS-safe request flow.
- Local/self-hosted ComfyUI workflows copied from Pixelle-Video `workflows/selfhost`.
- Local/free voice options only: Edge TTS, ComfyUI TTS workflows, and a generic Local Voice API for Omni Voice-style engines.
- OpenAI-compatible LLM providers with presets, default Base URLs, model fetching, custom model entry, and one-click connection tests.
- No RunningHub cloud configuration or workflow surface.

## Run

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

## Integration Notes

The product blueprint follows MoneyPrinterPlus because it has the broadest workflow coverage: generation, mixing, publishing-oriented screens, local TTS, and resource providers.

MoneyPrinterTurbo v1.2.8 is stronger for stock-video retrieval and final video assembly robustness, especially around Pexels/Pixabay key rotation, TLS verification, media validation, and task-oriented API structure. Morpheus uses that approach for the material adapter.

Pixelle-Video is strongest for modern local ComfyUI AI-video workflows and structured pipeline design. Morpheus imports only self-hosted workflow assets and exposes them as local options.

## License Notice

This repository includes license copies for the upstream projects in `docs/`. MoneyPrinterPlus contains non-commercial restrictions in its license text, so publish this repository privately unless you have permission for public/commercial redistribution.
