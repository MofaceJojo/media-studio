<h1 align="center">🎬 Morpheus Video Studio</h1>

<p align="center"><b>Content-first · zero-cost local stack · reliably rendered AI video workbench</b></p>

<p align="center"><b>English</b> | <a href="README.md">中文</a></p>

<p align="center">
  <a href="https://github.com/MofaceJojo/media-studio/stargazers"><img src="https://img.shields.io/github/stars/MofaceJojo/media-studio.svg" alt="Stargazers"></a>
  <a href="https://github.com/MofaceJojo/media-studio/issues"><img src="https://img.shields.io/github/issues/MofaceJojo/media-studio.svg" alt="Issues"></a>
  <a href="https://github.com/MofaceJojo/media-studio/blob/main/LICENSE"><img src="https://img.shields.io/github/license/MofaceJojo/media-studio.svg" alt="License"></a>
</p>

Morpheus Video Studio chains **content input, audio generation, video generation, digital-human narration, and asset reuse** into one production pipeline. Give it a script or a topic and it produces an upload-ready video — narration, images, storyboard, editing, and subtitles — entirely on your machine.

## 🎯 Three design goals

1. **Zero-cost generation** — apart from the script LLM API call, everything is free: local OmniVoice / Edge TTS narration, local ComfyUI images, free stock sources (Pexels / Pixabay), local HyperFrames layout rendering.
2. **Reliable output** — built around one invariant: *audio duration drives video duration*. Narration is generated first; its real measured length decides shot counts and hold times. Transitions never eat narration; every render passes a QA gate.
3. **Manual publishing, automated prep** — an accurate `final.srt` is written next to every video; uploads stay manual (avoiding platform risk-control), the system just preps the material.

## ✨ Highlights

- ✅ **Audio-driven pacing** — video length follows real narration length, cut frequency derived from it
- ✅ **Pacing profiles** — fast shorts / calm YouTube pacing, auto-selected for 16:9 landscape
- ✅ **Ken Burns motion** — stills always get slow zoom/pan; no more frozen frames
- ✅ **Final-video QA gate** — stream integrity, duration drift, frozen-picture and broken-narration detection on every render
- ✅ **SRT export** — cue timing from real per-narration audio durations
- ✅ **Local style presets** — photoreal / hand-drawn fantasy / eastern classical / cyberpunk / picture-book, all on local models
- ✅ **Workshop architecture** — content library, audio workshop, video workshop, digital human, asset library
- ✅ **Flexible aspect ratios** — 9:16 (Shorts/Douyin), 16:9 (YouTube), 1:1
- ✅ **Content recipes** — science / TCM / ranking / medical skeletons that pin script structure instead of drifting into life-insight chatter
- ✅ **No-human visual rules** — knowledge channels steer imagery to herbs, vessels, classical texts and fields, since local models mangle people
- ✅ **Classical text frames** — quotations are typeset from real characters, never drawn by AI (which produces gibberish)
- ✅ **BGM auto-ducking** — music dips under narration and swells back in the gaps
- ✅ **TTS auto-fallback** — an OmniVoice failure degrades to Edge TTS for that segment instead of failing the render
- ✅ **Resume** — an interrupted render reuses finished frames and only rebuilds the missing tail
- ✅ **Restyle workshop** — filter presets (instant) or AI repaint into animation styles, with optional reference-image guidance

## 📊 Pipeline

```
Script (input or LLM-generated)
   → TTS narration (OmniVoice / Edge TTS, real duration measured)
   → Shot planning (audio duration → shot count & hold times)
   → Per-frame production (ComfyUI image → HTML template → Ken Burns → segment)
   → Concat (padded-tail transitions, zero narration loss) + BGM
   → QA gate (duration / frozen frames / audio integrity)
   → final.mp4 + final.srt
```

## 🚀 Quick start

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [ffmpeg](https://ffmpeg.org/download.html) (`brew install ffmpeg` / `apt install ffmpeg`)
- Local [ComfyUI](https://github.com/Comfy-Org/ComfyUI) (image generation, default `http://127.0.0.1:8188`)
- Optional: [OmniVoice Studio](https://github.com/debpalash/OmniVoice-Studio) (high-quality local TTS; falls back to Edge TTS)

### Run

```bash
git clone https://github.com/MofaceJojo/media-studio.git
cd media-studio
uv run streamlit run web/app.py
```

The browser opens `http://localhost:8501`; configure your LLM API and local services on the **⚙️ Settings** page.

### Pages

| Page | Purpose |
|---|---|
| 🏠 Studio | Workbench home & quick create |
| 📚 Content Library | PDFs, texts, book excerpts, quotes |
| 🎙️ Audio Workshop | Reusable narration & voice assets |
| 🎬 Video Workshop | Script + assets + voice → final video |
| 🤖 Digital Human | Talking-head narration |
| 🗂️ Asset Library | Reuse of generated assets |
| ⚙️ Settings | LLM / ComfyUI / OmniVoice / local services |

## 📋 Recent updates

- ✅ **2026-07 late**: recipe visual rules (no humans in knowledge channels) and evidence grading; classical vertical-text templates; BGM auto-ducking; OmniVoice→Edge fallback; resume after interruption; podcast-style talking head; subtitle newline-leak fix; title language guard
- ✅ **2026-07 mid**: restyle workshop (filters + AI repaint + reference-image guidance); black-tail fix; OmniVoice voices in the custom-media workshop; Seedance (paid API) removed
- ✅ **2026-07 early**: shot-pacing constraints & calm YouTube profile; final-video QA gate; SRT export; flux-schnell (GGUF) workflow; OmniVoice idle-deadlock fix; `video.py` modular refactor; GitHub Actions CI
- ✅ **2026-07**: transitions no longer eat narration (padded tails); TTS transient-failure retry
- ✅ **2026-06**: Morpheus rebrand; quick-create flow; style tag system; stock-first media strategy

## 📚 Docs

| Doc | Contents |
|---|---|
| [docs/INSTALL.md](docs/INSTALL.md) | Full install guide (app / LLM key / ComfyUI + model manifest / OmniVoice) |
| [docs/upgrade-roadmap-2026-07.md](docs/upgrade-roadmap-2026-07.md) | Roadmap and comparisons with similar projects |
| [docs/HERMES-WORKFLOW.md](docs/HERMES-WORKFLOW.md) | Hermes delegation workflow (spec template + verification checklist) |
| [docs/FAQ.md](docs/FAQ.md) | FAQ |

## ❓ FAQ

See [docs/FAQ.md](docs/FAQ.md). Debug order for failed renders: check `frames/*_audio.wav` first, then `frames/*_image_shot_*.png`, then `frames/*_segment.mp4`, then the concat stage and backend service logs.

## 🤝 Credits

Built on an open-source prototype by AIDC-AI (Apache 2.0), with design inspiration from:

- [NarratoAI](https://github.com/linyqh/NarratoAI) — automated film commentary
- [ComfyKit](https://github.com/puke3615/ComfyKit) — ComfyUI workflow wrapper
- [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) / [OpenMontage](https://github.com/calesthio/OpenMontage) — pacing & QA ideas

## 📝 License

Apache 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
