import asyncio
import csv
import json
import os
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import httpx
from PIL import Image, ImageDraw, ImageFont
from loguru import logger


ProgressCallback = Optional[Callable[[str, float], None]]


@dataclass
class BookVideoResult:
    output_path: str
    task_dir: str
    pages: int
    duration: float


class BookPDFVideoPipeline:
    """PDF + narration audio -> regenerated picture-book video.

    This pipeline is intentionally self-contained so it can be called from
    Streamlit, a desktop shortcut, or n8n without manual intervention.
    """

    def __init__(self, core):
        self.core = core
        self.project_root = Path(__file__).resolve().parents[2]
        self.tool_dir = Path("/Users/mofacejojo/pdf-to-images-tool")
        self.pdf_converter = self.tool_dir / "pdf-to-images"
        self.ocr_tool = self.tool_dir / "ocr-images"

    async def __call__(
        self,
        pdf_path: str,
        audio_path: str,
        output_path: Optional[str] = None,
        title: str = "Book Video",
        workflow: str = "selfhost/image_book_page_redraw_dreamshaper_m4.json",
        width: int = 1024,
        height: int = 768,
        steps: int = 18,
        denoise: float = 0.68,
        cfg: float = 7.0,
        speed: float = 1.12,
        max_pages: Optional[int] = None,
        redraw_pages: bool = True,
        progress_callback: ProgressCallback = None,
    ) -> BookVideoResult:
        pdf = Path(pdf_path)
        audio = Path(audio_path)
        if not pdf.exists():
            raise FileNotFoundError(pdf)
        if not audio.exists():
            raise FileNotFoundError(audio)

        task_id = self._safe_stem(pdf.stem)
        task_dir = self.project_root / "output" / f"book_pdf_{task_id}"
        if task_dir.exists():
            shutil.rmtree(task_dir)
        for sub in ["pages", "ocr", "redrawn", "captions", "segments", "work"]:
            (task_dir / sub).mkdir(parents=True, exist_ok=True)

        final = Path(output_path) if output_path else task_dir / f"{task_id}_regenerated_video.mp4"
        final.parent.mkdir(parents=True, exist_ok=True)

        self._progress(progress_callback, "PDF 拆页", 0.03)
        page_paths = self._convert_pdf(pdf, task_dir / "pages")
        if max_pages:
            page_paths = page_paths[:max_pages]
        if not page_paths:
            raise RuntimeError("PDF did not produce any page images")

        self._progress(progress_callback, "OCR 识别页面文字", 0.08)
        page_texts = self._ocr_pages(page_paths, task_dir / "ocr" / "pages.tsv")

        self._progress(progress_callback, "生成重绘提示词", 0.12)
        prompts = await self._build_prompts(page_texts, title)
        (task_dir / "work" / "prompts.json").write_text(
            json.dumps(prompts, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if redraw_pages:
            redrawn = []
            total = len(page_paths)
            for idx, page in enumerate(page_paths, start=1):
                self._progress(progress_callback, f"ComfyUI 重绘页面 {idx}/{total}", 0.12 + 0.58 * idx / total)
                image_url = await self._redraw_page(
                    page=page,
                    prompt=prompts[idx - 1],
                    workflow=workflow,
                    width=width,
                    height=height,
                    steps=steps,
                    denoise=denoise,
                    cfg=cfg,
                )
                out = task_dir / "redrawn" / f"page_{idx:03d}.png"
                await self._download(image_url, out)
                redrawn.append(out)
        else:
            redrawn = page_paths

        self._progress(progress_callback, "生成字幕与节奏表", 0.74)
        sped_audio = task_dir / "work" / "narration.m4a"
        self._make_sped_audio(audio, sped_audio, speed=speed)
        duration = self._probe_duration(sped_audio)
        plan = self._make_timing_plan(page_texts, duration)
        (task_dir / "work" / "timing.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        overlays = self._make_caption_overlays(plan, task_dir / "captions")

        self._progress(progress_callback, "合成视频", 0.82)
        self._render_video(redrawn, overlays, plan, sped_audio, final, task_dir / "segments")

        self._progress(progress_callback, "完成", 1.0)
        return BookVideoResult(
            output_path=str(final),
            task_dir=str(task_dir),
            pages=len(page_paths),
            duration=self._probe_duration(final),
        )

    def _convert_pdf(self, pdf: Path, out_root: Path) -> list[Path]:
        subprocess.run(
            [str(self.pdf_converter), "--dpi", "180", "--format", "png", "--output", str(out_root), str(pdf)],
            check=True,
        )
        pages = sorted(out_root.rglob("page_*.png"))
        normalized = []
        normalized_dir = out_root / "normalized"
        normalized_dir.mkdir(exist_ok=True)
        for idx, src in enumerate(pages, start=1):
            dst = normalized_dir / f"page_{idx:03d}.png"
            shutil.copy2(src, dst)
            normalized.append(dst)
        return normalized

    def _ocr_pages(self, page_paths: list[Path], out_tsv: Path) -> list[str]:
        result = subprocess.run(
            [str(self.ocr_tool), *map(str, page_paths)],
            check=True,
            capture_output=True,
            text=True,
        )
        out_tsv.write_text(result.stdout, encoding="utf-8")
        texts = []
        for row in csv.reader(result.stdout.splitlines(), delimiter="\t"):
            text = row[2] if len(row) >= 3 else ""
            texts.append(self._clean_ocr(text))
        return texts

    async def _build_prompts(self, page_texts: list[str], title: str) -> list[str]:
        prompts = []
        for idx, text in enumerate(page_texts, start=1):
            if self.core.llm and self.core.config.get("llm", {}).get("api_key"):
                prompt = (
                    "Create one concise English image-generation prompt for a regenerated children's picture-book page. "
                    "Use the OCR text only as story context. Do not include readable text, logos, watermarks, or typography in the image. "
                    "Keep composition inspired by the reference page, but make it fresh, polished, warm, cinematic, and suitable for a bedtime story. "
                    f"Book title: {title}. Page {idx}. OCR text: {text or '(mostly illustration)'}"
                )
                try:
                    out = await self.core.llm(prompt, temperature=0.7, max_tokens=260)
                    prompts.append(str(out).strip())
                    continue
                except Exception as exc:
                    logger.warning(f"LLM prompt generation failed for page {idx}: {exc}")

            prompts.append(
                "beautiful regenerated children's bedtime picture-book illustration, "
                "soft moonlit colors, cozy gentle atmosphere, hand-painted storybook style, "
                "clean composition, no text, no watermark, inspired by the reference page"
                + (f", scene context: {text}" if text else "")
            )
        return prompts

    async def _redraw_page(
        self,
        page: Path,
        prompt: str,
        workflow: str,
        width: int,
        height: int,
        steps: int,
        denoise: float,
        cfg: float,
    ) -> str:
        result = await self.core.media(
            prompt=prompt,
            workflow=workflow,
            media_type="image",
            image=str(page),
            width=width,
            height=height,
            steps=steps,
            denoise=denoise,
            cfg=cfg,
            negative_prompt=(
                "text, words, letters, logo, watermark, blurry, low quality, distorted, "
                "scary, photorealistic, bad face, asymmetrical face, deformed eyes, "
                "bad anatomy, bad hands, extra fingers, missing fingers, fused fingers"
            ),
        )
        return result.url

    async def _download(self, url: str, out: Path):
        if url.startswith("http://") or url.startswith("https://"):
            timeout = httpx.Timeout(connect=10.0, read=120.0, write=60.0, pool=60.0)
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                response = await client.get(url)
                response.raise_for_status()
                out.write_bytes(response.content)
        else:
            shutil.copy2(url, out)

    def _make_sped_audio(self, audio: Path, out: Path, speed: float):
        speed = max(0.5, min(2.0, speed))
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(audio), "-filter:a", f"atempo={speed}",
                "-c:a", "aac", "-b:a", "192k", str(out)
            ],
            check=True,
        )

    def _make_timing_plan(self, page_texts: list[str], duration: float) -> list[dict]:
        weights = [max(6, min(len(t), 85)) if t else 7 for t in page_texts]
        base = 2.6
        remaining = max(0.0, duration - base * len(weights))
        total_weight = sum(weights)
        start = 0.0
        plan = []
        for idx, (text, weight) in enumerate(zip(page_texts, weights), start=1):
            page_duration = base + remaining * weight / total_weight
            plan.append({"page": idx, "start": start, "duration": page_duration, "caption": text})
            start += page_duration
        if plan:
            plan[-1]["duration"] += duration - sum(p["duration"] for p in plan)
        return plan

    def _make_caption_overlays(self, plan: list[dict], out_dir: Path) -> list[Path]:
        out_dir.mkdir(exist_ok=True)
        font_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        font = ImageFont.truetype(font_path, 48)
        overlays = []
        for item in plan:
            text = "\n".join(textwrap.wrap(item["caption"], width=36))
            image = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
            if text:
                draw = ImageDraw.Draw(image)
                lines = text.splitlines()
                boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=3) for line in lines]
                widths = [b[2] - b[0] for b in boxes]
                heights = [b[3] - b[1] for b in boxes]
                line_gap = 10
                text_w = max(widths)
                text_h = sum(heights) + line_gap * (len(lines) - 1)
                x = (1920 - text_w) // 2
                y = 1080 - text_h - 72
                pad_x, pad_y = 32, 24
                draw.rounded_rectangle(
                    (x - pad_x, y - pad_y, x + text_w + pad_x, y + text_h + pad_y),
                    radius=18,
                    fill=(0, 0, 0, 118),
                )
                yy = y
                for line, height in zip(lines, heights):
                    line_box = draw.textbbox((0, 0), line, font=font, stroke_width=3)
                    xx = (1920 - (line_box[2] - line_box[0])) // 2
                    draw.text((xx, yy), line, font=font, fill="white", stroke_width=3, stroke_fill=(0, 0, 0, 230))
                    yy += height + line_gap
            out = out_dir / f"overlay_{item['page']:03d}.png"
            image.save(out)
            overlays.append(out)
        return overlays

    def _render_video(
        self,
        images: list[Path],
        overlays: list[Path],
        plan: list[dict],
        audio: Path,
        final: Path,
        segment_dir: Path,
    ):
        if segment_dir.exists():
            shutil.rmtree(segment_dir)
        segment_dir.mkdir(parents=True)
        segments = []
        for image, overlay, item in zip(images, overlays, plan):
            out = segment_dir / f"seg_{item['page']:03d}.mp4"
            filter_graph = (
                "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,"
                "setsar=1,format=rgba[base];"
                "[base][1:v]overlay=0:0,format=yuv420p[v]"
            )
            subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-loop", "1", "-t", f"{item['duration']:.6f}", "-i", str(image),
                    "-loop", "1", "-t", f"{item['duration']:.6f}", "-i", str(overlay),
                    "-filter_complex", filter_graph,
                    "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "16", "-pix_fmt", "yuv420p", str(out),
                ],
                check=True,
            )
            segments.append(out)

        list_path = segment_dir / "segments.txt"
        list_path.write_text("".join(f"file '{seg}'\n" for seg in segments), encoding="utf-8")
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(list_path),
                "-i", str(audio),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(final),
            ],
            check=True,
        )

    def _probe_duration(self, path: Path) -> float:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nk=1:nw=1", str(path)]
        )
        return float(out.decode().strip())

    def _clean_ocr(self, text: str) -> str:
        keep = []
        for ch in text:
            keep.append(ch if ch.isalnum() or ch in " .,;:!?\"'-" else " ")
        cleaned = " ".join("".join(keep).split())
        replacements = {
            "MOONE": "MOON",
            "Margatet": "Margaret",
            "199l": "1991",
            "wwww MN ww 3 3 wwww. ": "",
            ", And": "And",
        }
        for src, dst in replacements.items():
            cleaned = cleaned.replace(src, dst)
        return cleaned

    def _safe_stem(self, value: str) -> str:
        safe = "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")
        return safe or "book"

    def _progress(self, callback: ProgressCallback, message: str, value: float):
        logger.info(f"[BookPDF] {value:.0%} {message}")
        if callback:
            callback(message, value)
