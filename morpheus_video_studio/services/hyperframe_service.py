"""
HyperFrames-backed media rendering service.

This service creates a small temporary HyperFrames project and renders a video
clip with the local HyperFrames CLI.
"""

import asyncio
import hashlib
import html
import re
import shlex
import textwrap
import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

from morpheus_video_studio.config import config_manager
from morpheus_video_studio.models.media import MediaResult


class HyperFrameService:
    """Local HyperFrames video renderer."""

    def __init__(self, config: dict):
        self.config = config

    async def render_media(
        self,
        prompt: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration: Optional[float] = None,
        index: Optional[int] = None,
        **params,
    ) -> MediaResult:
        """
        Render a simple animated video clip from prompt text.

        HyperFrames is a renderer, not a ComfyUI-compatible image model. This
        gives Morpheus a local video provider for places where video templates
        otherwise require a ComfyUI video workflow.
        """
        config_manager.reload()
        hf_config = config_manager.get_hyperframe_config()
        if not hf_config.get("enabled", True):
            raise RuntimeError("HyperFrame is disabled in config.")

        final_width = int(width or 1080)
        final_height = int(height or 1920)
        final_duration = max(float(duration or params.get("duration") or 5.0), 1.0)
        fps = int(hf_config.get("fps") or 30)
        quality = hf_config.get("quality") or "draft"
        timeout = int(hf_config.get("timeout_seconds") or 300)
        command = hf_config.get("command") or "npx --yes hyperframes"

        job_id = uuid.uuid4().hex
        job_dir = Path("temp") / "hyperframe" / f"frame_{index or 0}_{job_id}"
        output_dir = Path("output") / "hyperframe"
        output_path = output_dir / f"{job_id}.mp4"
        job_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        (job_dir / "index.html").write_text(
            self._build_composition_html(
                prompt=prompt,
                width=final_width,
                height=final_height,
                duration=final_duration,
            ),
            encoding="utf-8",
        )

        argv = [
            *shlex.split(command),
            "render",
            str(job_dir),
            "--output",
            str(output_path.resolve()),
            "--quality",
            quality,
            "--fps",
            str(fps),
        ]
        logger.info(f"🎞️  Rendering HyperFrame clip: {' '.join(argv)}")

        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            proc.kill()
            await proc.communicate()
            raise RuntimeError(f"HyperFrame render timed out after {timeout}s") from exc

        stdout_text = stdout.decode(errors="replace").strip()
        stderr_text = stderr.decode(errors="replace").strip()
        if proc.returncode != 0:
            details = stderr_text or stdout_text or "unknown error"
            raise RuntimeError(f"HyperFrame render failed: {details}")

        if not output_path.exists():
            raise RuntimeError(f"HyperFrame render completed but output was not created: {output_path}")

        logger.info(f"✅ HyperFrame video generated: {output_path}")
        return MediaResult(media_type="video", url=str(output_path), duration=final_duration)

    def _build_composition_html(self, prompt: str, width: int, height: int, duration: float) -> str:
        """
        Build a deterministic HyperFrames composition.

        HyperFrame should provide a moving visual bed, not a second subtitle layer.
        So we convert the prompt into visual tokens and palette cues, then render an
        abstract motion-graphics scene instead of centering the raw prompt text.
        """
        brief = self._build_visual_brief(prompt)
        safe_duration = f"{duration:.2f}"
        padding = max(42, int(min(width, height) * 0.065))
        chip_font_size = max(18, min(30, int(width * 0.022)))
        label_font_size = max(16, min(24, int(width * 0.017)))

        chips_html = "\n".join(
            f'<div class="chip">{html.escape(token)}</div>' for token in brief["tokens"]
        )
        accent_bars = "\n".join(
            f'<div class="bar bar-{idx + 1}"></div>' for idx in range(4)
        )
        floating_orbs = "\n".join(
            f'<div class="orb orb-{idx + 1}"></div>' for idx in range(5)
        )

        return textwrap.dedent(f"""\
            <!doctype html>
            <html>
            <head>
              <meta charset="utf-8" />
              <meta name="viewport" content="width=device-width, initial-scale=1" />
              <style>
                :root {{
                  --bg-1: {brief["bg_1"]};
                  --bg-2: {brief["bg_2"]};
                  --bg-3: {brief["bg_3"]};
                  --accent-1: {brief["accent_1"]};
                  --accent-2: {brief["accent_2"]};
                  --accent-3: {brief["accent_3"]};
                  --ink: rgba(247, 243, 235, 0.94);
                  --soft-ink: rgba(247, 243, 235, 0.68);
                }}
                html, body {{
                  margin: 0;
                  width: 100%;
                  height: 100%;
                  overflow: hidden;
                  background: #0f1116;
                  font-family: "Avenir Next", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
                }}
                [data-composition-id="morpheus-hyperframe"] {{
                  position: relative;
                  width: {width}px;
                  height: {height}px;
                  overflow: hidden;
                  background:
                    radial-gradient(circle at 14% 18%, color-mix(in srgb, var(--accent-1) 42%, transparent), transparent 26%),
                    radial-gradient(circle at 82% 20%, color-mix(in srgb, var(--accent-2) 36%, transparent), transparent 24%),
                    radial-gradient(circle at 76% 82%, color-mix(in srgb, var(--accent-3) 32%, transparent), transparent 22%),
                    linear-gradient(145deg, var(--bg-1) 0%, var(--bg-2) 48%, var(--bg-3) 100%);
                }}
                .noise {{
                  position: absolute;
                  inset: 0;
                  opacity: 0.12;
                  mix-blend-mode: soft-light;
                  background-image:
                    linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px),
                    linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px);
                  background-size: 34px 34px;
                  animation: drift 18s linear infinite;
                }}
                .frame {{
                  position: absolute;
                  inset: {padding}px;
                  border: 1px solid rgba(255,255,255,0.12);
                  border-radius: 32px;
                  backdrop-filter: blur(2px);
                }}
                .bars {{
                  position: absolute;
                  inset: 0;
                }}
                .bar {{
                  position: absolute;
                  border-radius: 999px;
                  filter: blur(0.2px);
                  opacity: 0.72;
                  transform-origin: center;
                }}
                .bar-1 {{
                  width: {max(220, int(width * 0.42))}px;
                  height: {max(16, int(height * 0.012))}px;
                  top: 18%;
                  left: 8%;
                  background: linear-gradient(90deg, transparent, var(--accent-1), transparent);
                  animation: slideA {max(duration * 0.9, 4.0):.2f}s ease-in-out infinite alternate;
                }}
                .bar-2 {{
                  width: {max(180, int(width * 0.34))}px;
                  height: {max(14, int(height * 0.01))}px;
                  top: 68%;
                  right: 10%;
                  background: linear-gradient(90deg, transparent, var(--accent-2), transparent);
                  animation: slideB {max(duration * 1.1, 4.8):.2f}s ease-in-out infinite alternate;
                }}
                .bar-3 {{
                  width: {max(140, int(width * 0.24))}px;
                  height: {max(12, int(height * 0.008))}px;
                  top: 32%;
                  right: 16%;
                  background: linear-gradient(90deg, transparent, var(--accent-3), transparent);
                  animation: pulse {max(duration * 0.8, 3.2):.2f}s ease-in-out infinite;
                }}
                .bar-4 {{
                  width: {max(200, int(width * 0.36))}px;
                  height: {max(12, int(height * 0.008))}px;
                  bottom: 16%;
                  left: 12%;
                  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.65), transparent);
                  animation: slideC {max(duration * 1.15, 5.2):.2f}s ease-in-out infinite alternate;
                }}
                .orbs {{
                  position: absolute;
                  inset: 0;
                }}
                .orb {{
                  position: absolute;
                  border-radius: 50%;
                  filter: blur(18px);
                  opacity: 0.28;
                }}
                .orb-1 {{ width: 240px; height: 240px; left: 10%; top: 22%; background: var(--accent-1); animation: floatA {max(duration * 1.05, 5.0):.2f}s ease-in-out infinite alternate; }}
                .orb-2 {{ width: 180px; height: 180px; right: 12%; top: 18%; background: var(--accent-2); animation: floatB {max(duration * 0.95, 4.4):.2f}s ease-in-out infinite alternate; }}
                .orb-3 {{ width: 220px; height: 220px; right: 18%; bottom: 14%; background: var(--accent-3); animation: floatC {max(duration * 1.15, 5.8):.2f}s ease-in-out infinite alternate; }}
                .orb-4 {{ width: 140px; height: 140px; left: 18%; bottom: 20%; background: rgba(255,255,255,0.34); animation: floatD {max(duration * 0.9, 4.2):.2f}s ease-in-out infinite alternate; }}
                .orb-5 {{ width: 110px; height: 110px; left: 46%; top: 44%; background: color-mix(in srgb, var(--accent-1) 50%, var(--accent-2)); animation: floatE {max(duration * 0.85, 4.0):.2f}s ease-in-out infinite alternate; }}
                .focus-panel {{
                  position: absolute;
                  left: 50%;
                  top: 50%;
                  transform: translate(-50%, -50%);
                  width: {max(360, int(width * 0.62))}px;
                  height: {max(420, int(height * 0.42))}px;
                  border-radius: 34px;
                  background:
                    linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.05));
                  border: 1px solid rgba(255,255,255,0.14);
                  box-shadow:
                    0 30px 80px rgba(0,0,0,0.28),
                    inset 0 1px 0 rgba(255,255,255,0.16);
                  overflow: hidden;
                  animation: breathe {max(duration * 0.75, 3.0):.2f}s ease-in-out infinite;
                }}
                .focus-grid {{
                  position: absolute;
                  inset: 0;
                  background:
                    linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px),
                    linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px);
                  background-size: 44px 44px;
                  mask-image: linear-gradient(180deg, rgba(255,255,255,0.85), transparent 90%);
                }}
                .focus-core {{
                  position: absolute;
                  inset: 12% 14%;
                  border-radius: 28px;
                  border: 1px solid rgba(255,255,255,0.1);
                  background:
                    radial-gradient(circle at 50% 44%, rgba(255,255,255,0.18), transparent 26%),
                    radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--accent-1) 30%, transparent), transparent 52%),
                    linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
                }}
                .ring {{
                  position: absolute;
                  left: 50%;
                  top: 50%;
                  transform: translate(-50%, -50%);
                  border-radius: 50%;
                  border: 1px solid rgba(255,255,255,0.18);
                }}
                .ring-1 {{
                  width: 46%;
                  aspect-ratio: 1;
                  animation: spinA {max(duration * 1.4, 7.0):.2f}s linear infinite;
                }}
                .ring-2 {{
                  width: 62%;
                  aspect-ratio: 1;
                  border-color: rgba(255,255,255,0.1);
                  animation: spinB {max(duration * 1.8, 9.0):.2f}s linear infinite;
                }}
                .topic {{
                  position: absolute;
                  left: {padding}px;
                  right: {padding}px;
                  bottom: {padding}px;
                  display: flex;
                  flex-wrap: wrap;
                  gap: 12px;
                  justify-content: center;
                }}
                .chip {{
                  padding: 10px 18px;
                  border-radius: 999px;
                  border: 1px solid rgba(255,255,255,0.14);
                  background: rgba(9, 12, 18, 0.32);
                  color: var(--ink);
                  font-size: {chip_font_size}px;
                  letter-spacing: 0.02em;
                  backdrop-filter: blur(8px);
                  box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
                }}
                .label {{
                  position: absolute;
                  top: {padding}px;
                  left: {padding}px;
                  color: var(--soft-ink);
                  font-size: {label_font_size}px;
                  letter-spacing: 0.12em;
                  text-transform: uppercase;
                }}
                @keyframes drift {{ from {{ transform: translate3d(0,0,0); }} to {{ transform: translate3d(-24px,-18px,0); }} }}
                @keyframes slideA {{ from {{ transform: translateX(-12px) scaleX(0.92); }} to {{ transform: translateX(26px) scaleX(1.05); }} }}
                @keyframes slideB {{ from {{ transform: translateX(10px); }} to {{ transform: translateX(-24px); }} }}
                @keyframes slideC {{ from {{ transform: translateX(-10px) scaleX(0.86); }} to {{ transform: translateX(22px) scaleX(1.08); }} }}
                @keyframes pulse {{ 0%,100% {{ opacity: 0.35; }} 50% {{ opacity: 0.9; }} }}
                @keyframes floatA {{ from {{ transform: translate3d(-24px,-16px,0); }} to {{ transform: translate3d(26px,18px,0); }} }}
                @keyframes floatB {{ from {{ transform: translate3d(18px,-12px,0); }} to {{ transform: translate3d(-18px,22px,0); }} }}
                @keyframes floatC {{ from {{ transform: translate3d(0,-22px,0); }} to {{ transform: translate3d(-30px,14px,0); }} }}
                @keyframes floatD {{ from {{ transform: translate3d(-10px,16px,0); }} to {{ transform: translate3d(20px,-14px,0); }} }}
                @keyframes floatE {{ from {{ transform: translate3d(12px,-8px,0) scale(0.94); }} to {{ transform: translate3d(-14px,16px,0) scale(1.08); }} }}
                @keyframes breathe {{ 0%,100% {{ transform: translate(-50%, -50%) scale(0.985); }} 50% {{ transform: translate(-50%, -50%) scale(1.02); }} }}
                @keyframes spinA {{ from {{ transform: translate(-50%, -50%) rotate(0deg); }} to {{ transform: translate(-50%, -50%) rotate(360deg); }} }}
                @keyframes spinB {{ from {{ transform: translate(-50%, -50%) rotate(360deg); }} to {{ transform: translate(-50%, -50%) rotate(0deg); }} }}
              </style>
            </head>
            <body>
              <div data-composition-id="morpheus-hyperframe" data-start="0" data-duration="{safe_duration}" data-width="{width}" data-height="{height}" data-track-index="0">
                <div class="noise"></div>
                <div class="frame"></div>
                <div class="bars">{accent_bars}</div>
                <div class="orbs">{floating_orbs}</div>
                <div class="focus-panel">
                  <div class="focus-grid"></div>
                  <div class="focus-core"></div>
                  <div class="ring ring-1"></div>
                  <div class="ring ring-2"></div>
                </div>
                <div class="label">{html.escape(brief["label"])}</div>
                <div class="topic">{chips_html}</div>
              </div>
            </body>
            </html>
        """)

    def _build_visual_brief(self, prompt: str) -> dict:
        """Convert prompt text into a compact visual brief for HyperFrame."""
        cleaned = self._strip_prompt_prefix(prompt)
        seed = hashlib.md5(cleaned.encode("utf-8")).hexdigest()
        bg_1, bg_2, bg_3, accent_1, accent_2, accent_3 = self._palette_from_seed(seed)
        tokens = self._extract_tokens(cleaned)
        label = self._build_label(cleaned, tokens)
        return {
            "tokens": tokens,
            "label": label,
            "bg_1": bg_1,
            "bg_2": bg_2,
            "bg_3": bg_3,
            "accent_1": accent_1,
            "accent_2": accent_2,
            "accent_3": accent_3,
        }

    def _strip_prompt_prefix(self, prompt: str) -> str:
        cleaned = (prompt or "").strip()
        comfy_config = config_manager.get_comfyui_config()
        prefixes = [
            comfy_config.get("image", {}).get("prompt_prefix", ""),
            comfy_config.get("video", {}).get("prompt_prefix", ""),
        ]
        for prefix in prefixes:
            prefix = (prefix or "").strip().rstrip(",")
            if not prefix:
                continue
            prefixed = f"{prefix}, "
            if cleaned.startswith(prefixed):
                return cleaned[len(prefixed):].strip()
            if cleaned == prefix:
                return ""
        return cleaned

    def _extract_tokens(self, prompt: str) -> list[str]:
        """Extract short theme tokens instead of dumping the full prompt on screen."""
        cleaned = re.sub(r"\s+", " ", (prompt or "").strip())
        if not cleaned:
            return ["motion", "story", "visual"]

        if any("\u4e00" <= ch <= "\u9fff" for ch in cleaned):
            normalized = cleaned
            for marker in ("中的", "关于", "围绕", "聚焦", "展示", "呈现"):
                normalized = normalized.replace(marker, "|")
            normalized = re.sub(r"\s*(与|和|及|以及|并且|结合|搭配)\s*", "|", normalized)
            parts = re.split(r"[|，。！？；、,.!?:/\-\n]+", normalized)
            tokens = [self._clean_chinese_token(part) for part in parts if part.strip()]
        else:
            parts = re.split(r"[,.;:!?/\-\n]+", cleaned)
            tokens = []
            for part in parts:
                words = [word for word in part.strip().split() if word]
                if words:
                    tokens.append(" ".join(words[:3]))

        tokens = [token for token in tokens if token]
        deduped: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            lowered = token.lower()
            if lowered not in seen:
                deduped.append(token)
                seen.add(lowered)
            if len(deduped) >= 4:
                break
        return deduped or ["motion", "story", "visual"]

    def _clean_chinese_token(self, token: str) -> str:
        token = re.sub(r"\s+", "", token.strip())
        token = re.sub(r"^(一个|一些|一种|这段|这个)", "", token)
        return token[:8]

    def _build_label(self, prompt: str, tokens: list[str]) -> str:
        if not prompt:
            return "MORPHEUS VISUAL"
        if any("\u4e00" <= ch <= "\u9fff" for ch in prompt):
            return tokens[0] if tokens else "MORPHEUS VISUAL"
        compact = re.sub(r"[^A-Za-z0-9\s]", " ", prompt)
        compact = re.sub(r"\s+", " ", compact).strip()
        words = compact.split()[:2]
        return " / ".join(word.upper() for word in words) if words else "MORPHEUS VISUAL"

    def _palette_from_seed(self, seed: str) -> tuple[str, str, str, str, str, str]:
        """Generate a deterministic cinematic palette from prompt hash."""
        values = [int(seed[idx:idx + 2], 16) for idx in range(0, 12, 2)]
        bg_1 = f"rgb({18 + values[0] % 28}, {20 + values[1] % 36}, {32 + values[2] % 44})"
        bg_2 = f"rgb({28 + values[3] % 34}, {34 + values[4] % 40}, {48 + values[5] % 46})"
        bg_3 = f"rgb({10 + values[2] % 18}, {14 + values[4] % 24}, {22 + values[0] % 30})"
        accent_1 = f"rgb({118 + values[1] % 110}, {88 + values[2] % 120}, {170 + values[3] % 70})"
        accent_2 = f"rgb({82 + values[4] % 130}, {166 + values[5] % 70}, {138 + values[0] % 90})"
        accent_3 = f"rgb({214 + values[2] % 40}, {134 + values[3] % 70}, {82 + values[4] % 90})"
        return bg_1, bg_2, bg_3, accent_1, accent_2, accent_3
