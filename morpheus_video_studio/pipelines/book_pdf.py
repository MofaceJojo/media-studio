import asyncio
import csv
import json
import os
import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Any

import httpx
from PIL import Image, ImageDraw, ImageFont
from loguru import logger

from morpheus_video_studio.config import config_manager
from morpheus_video_studio.services.notebooklm_service import NotebookLMService
from morpheus_video_studio.utils.document_text import extract_text_from_document


ProgressCallback = Optional[Callable[[str, float], None]]

SUPPORTED_DOCUMENT_SUFFIXES = {".pdf", ".doc", ".docx", ".ppt", ".pptx"}


@dataclass
class BookVideoResult:
    output_path: str
    task_dir: str
    pages: int
    duration: float


class BookPDFVideoPipeline:
    """Document + optional narration audio -> regenerated picture-book video.

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
        audio_path: Optional[str] = None,
        output_path: Optional[str] = None,
        title: str = "Book Video",
        content_mode: str = "ai_script",
        analysis_backend: str = "local",
        n_scenes: int = 6,
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
        source = Path(pdf_path)
        if not source.exists():
            raise FileNotFoundError(source)
        if source.suffix.lower() not in SUPPORTED_DOCUMENT_SUFFIXES:
            raise ValueError(f"暂不支持的文档格式：{source.suffix or source.name}")
        audio = Path(audio_path) if audio_path else None
        if audio and not audio.exists():
            raise FileNotFoundError(audio)

        task_id = self._safe_stem(source.stem)
        task_dir = self.project_root / "output" / f"book_document_{task_id}"
        if task_dir.exists():
            shutil.rmtree(task_dir)
        for sub in ["pages", "ocr", "redrawn", "captions", "segments", "work"]:
            (task_dir / sub).mkdir(parents=True, exist_ok=True)

        final = Path(output_path) if output_path else task_dir / f"{task_id}_regenerated_video.mp4"
        final.parent.mkdir(parents=True, exist_ok=True)

        if content_mode == "ai_script" and source.suffix.lower() != ".pdf":
            self._progress(progress_callback, "提取文档文字", 0.08)
            page_texts = self._extract_document_page_texts(source)
            return await self._generate_video_from_pdf_content(
                page_texts=page_texts,
                title=title or source.stem,
                task_dir=task_dir,
                output_path=final,
                source_path=source,
                analysis_backend=analysis_backend,
                n_scenes=n_scenes,
                audio_path=audio,
                speed=speed,
                progress_callback=progress_callback,
            )

        pdf = self._ensure_pdf(source, task_dir / "work")

        self._progress(progress_callback, "文档拆页", 0.03)
        page_paths = self._convert_pdf(pdf, task_dir / "pages")
        if max_pages:
            page_paths = page_paths[:max_pages]
        if not page_paths:
            raise RuntimeError("文档没有生成任何页面图片")

        self._progress(progress_callback, "OCR 识别页面文字", 0.08)
        page_texts = self._ocr_pages(page_paths, task_dir / "ocr" / "pages.tsv")

        if content_mode == "ai_script":
            return await self._generate_video_from_pdf_content(
                page_texts=page_texts,
                title=title or source.stem,
                task_dir=task_dir,
                output_path=final,
                source_path=source,
                analysis_backend=analysis_backend,
                n_scenes=n_scenes,
                audio_path=audio,
                speed=speed,
                progress_callback=progress_callback,
            )

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
                self._ensure_still_image(out)
                redrawn.append(out)
        else:
            redrawn = page_paths

        self._progress(progress_callback, "生成字幕与节奏表", 0.74)
        sped_audio = task_dir / "work" / "narration.m4a"
        if audio:
            self._make_sped_audio(audio, sped_audio, speed=speed)
            duration = self._probe_duration(sped_audio)
            plan = self._make_timing_plan(page_texts, duration)
        else:
            narrations = await self._build_narrations(page_texts, title)
            (task_dir / "work" / "narrations.json").write_text(
                json.dumps(narrations, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            narration_audios = await self._make_generated_audio(
                narrations=narrations,
                out_dir=task_dir / "work" / "narration_pages",
                speed=speed,
                progress_callback=progress_callback,
            )
            self._concat_audio(narration_audios, sped_audio)
            duration = self._probe_duration(sped_audio)
            plan = self._make_timing_plan_from_durations(narrations, narration_audios)
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

    async def _generate_video_from_pdf_content(
        self,
        page_texts: list[str],
        title: str,
        task_dir: Path,
        output_path: Path,
        source_path: Path,
        analysis_backend: str,
        n_scenes: int,
        audio_path: Optional[Path],
        speed: float,
        progress_callback: ProgressCallback = None,
    ) -> BookVideoResult:
        self._progress(progress_callback, "AI 解读文档内容", 0.16)
        script = await self._build_video_script(
            page_texts=page_texts,
            title=title,
            n_scenes=n_scenes,
            task_dir=task_dir,
            source_path=source_path,
            analysis_backend=analysis_backend,
            progress_callback=progress_callback,
        )
        (task_dir / "work" / "ai_script.txt").write_text(script, encoding="utf-8")

        self._progress(progress_callback, "按文案生成视频", 0.24)

        def standard_progress(event: Any):
            progress = getattr(event, "progress", 0.0)
            action = getattr(event, "action", None)
            event_type = getattr(event, "event_type", "生成视频")
            frame_current = getattr(event, "frame_current", None)
            frame_total = getattr(event, "frame_total", None)
            label = action or event_type
            if frame_current and frame_total:
                label = f"{label} {frame_current}/{frame_total}"
            self._progress(progress_callback, label, 0.24 + 0.74 * float(progress))

        params = {
            "mode": "fixed",
            "split_mode": "line",
            "title": title,
            "n_scenes": n_scenes,
            "output_path": str(output_path),
            "frame_template": "1080x1920/video_default.html",
            "media_workflow": "stock/turbo",
            "media_strategy": "stock_turbo",
            "stock_selection_mode": "sequential",
            "prompt_prefix": "cinematic Macau travel guide footage, warm documentary style, lively city details",
            "tts_inference_mode": "local",
            "tts_speed": speed,
            "subtitle_enabled": True,
            "subtitle_customization_enabled": True,
            "subtitle_position": "bottom",
            "subtitle_size": 54,
        }
        if audio_path:
            logger.info("Uploaded narration audio is ignored in AI script mode; standard TTS is generated from the AI script.")

        result = await self.core.generate_video(
            text=script,
            pipeline="standard",
            progress_callback=standard_progress,
            **params,
        )

        self._progress(progress_callback, "完成", 1.0)
        return BookVideoResult(
            output_path=result.video_path,
            task_dir=str(task_dir),
            pages=len(page_texts),
            duration=result.duration,
        )

    async def _build_video_script(
        self,
        page_texts: list[str],
        title: str,
        n_scenes: int,
        task_dir: Path,
        source_path: Path,
        analysis_backend: str,
        progress_callback: ProgressCallback = None,
    ) -> str:
        if analysis_backend == "notebooklm":
            try:
                report_text = await self._build_notebooklm_report(
                    source_path=source_path,
                    title=title,
                    task_dir=task_dir,
                    progress_callback=progress_callback,
                )
                script = await self._build_video_script_from_report(report_text, title, n_scenes)
                (task_dir / "work" / "notebooklm_script_source.txt").write_text(
                    report_text,
                    encoding="utf-8",
                )
                return script
            except Exception as exc:
                logger.warning(f"NotebookLM 解读失败，回退本地 LLM: {exc}")
                self._progress(progress_callback, "NotebookLM 不可用，回退本地解读", 0.19)

        return await self._build_video_script_from_pdf(page_texts, title, n_scenes)

    async def _build_video_script_from_pdf(self, page_texts: list[str], title: str, n_scenes: int) -> str:
        content = "\n".join(
            f"第{idx}页：{text}"
            for idx, text in enumerate(page_texts, start=1)
            if text
        )
        content = content[:12000]
        if not content.strip():
            raise RuntimeError("文档没有识别出足够文字，无法让 AI 解读生成文案。")
        if not (self.core.llm and self.core.config.get("llm", {}).get("api_key")):
            raise RuntimeError("需要配置 LLM，才能解读文档内容并生成视频文案。")

        prompt = (
            "你是短视频内容策划。请阅读下面从文档中提取到的资料，先理解内容，"
            "再重新创作一条适合短视频的中文旁白文案。不要照抄 PDF 原文，不要逐页复述，"
            "要提炼重点、组织游玩逻辑、给出有用建议，语气自然、有画面感。"
            f"\n标题：{title}"
            f"\n请输出 {n_scenes} 行，每行就是一个分镜旁白。"
            "每行 20-45 个汉字左右，不要编号，不要 Markdown，不要解释。"
            f"\n\n文档内容：\n{content}"
        )
        out = await self.core.llm(prompt, temperature=0.72, max_tokens=900)
        lines = [
            self._clean_narration(line.lstrip("0123456789.-、)） "))
            for line in str(out).splitlines()
            if self._clean_narration(line)
        ]
        if len(lines) < 2:
            lines = [self._clean_narration(part) for part in str(out).replace("。", "。\n").splitlines()]
            lines = [line for line in lines if line]
        if not lines:
            raise RuntimeError("AI 没有生成可用的视频文案。")
        return "\n".join(lines[:n_scenes])

    async def _build_video_script_from_report(self, report_text: str, title: str, n_scenes: int) -> str:
        content = report_text[:14000].strip()
        if not content:
            raise RuntimeError("NotebookLM 没有返回可用报告内容。")

        if self.core.llm and self.core.config.get("llm", {}).get("api_key"):
            prompt = (
                "你是短视频内容策划。下面是一份由 NotebookLM 根据原始文档整理出来的结构化报告。"
                "请基于这份报告，重新创作一条适合短视频的中文旁白文案。"
                "不要照抄原文，不要逐段复述报告，要提炼重点、组织顺序、增强画面感和节奏感。"
                f"\n标题：{title}"
                f"\n请输出 {n_scenes} 行，每行就是一个分镜旁白。"
                "每行 20-45 个汉字左右，不要编号，不要 Markdown，不要解释。"
                f"\n\nNotebookLM 报告：\n{content}"
            )
            out = await self.core.llm(prompt, temperature=0.72, max_tokens=900)
            lines = [
                self._clean_narration(line.lstrip("0123456789.-、)） "))
                for line in str(out).splitlines()
                if self._clean_narration(line)
            ]
            if len(lines) >= 2:
                return "\n".join(lines[:n_scenes])

        return self._script_from_paragraphs(report_text, n_scenes)

    async def _build_notebooklm_report(
        self,
        source_path: Path,
        title: str,
        task_dir: Path,
        progress_callback: ProgressCallback = None,
    ) -> str:
        notebooklm_config = config_manager.get_notebooklm_config()
        if not notebooklm_config.get("enabled"):
            raise RuntimeError("NotebookLM Beta 尚未在 Settings 中启用。")

        self._progress(progress_callback, "NotebookLM 解析文档", 0.18)
        service = NotebookLMService(notebooklm_config)
        notebook_source = self._prepare_notebooklm_source(source_path, task_dir / "work")
        report_text = await service.generate_report_from_file(
            file_path=notebook_source,
            title=title or notebook_source.stem,
            output_dir=task_dir / "work",
            extra_instructions=(
                "请保留清晰的章节结构，优先提炼适合做短视频的关键信息、路线、观点、案例、清单和结论。"
            ),
        )
        return report_text

    def _script_from_paragraphs(self, text: str, n_scenes: int) -> str:
        lines = []
        for raw_line in text.splitlines():
            cleaned = self._clean_narration(raw_line.lstrip("#*-•0123456789.、)） ").strip())
            if len(cleaned) < 12:
                continue
            lines.append(cleaned[:45])
            if len(lines) >= n_scenes:
                break
        if not lines:
            raise RuntimeError("NotebookLM 报告存在，但没有提炼出可用的视频文案。")
        return "\n".join(lines)

    def _prepare_notebooklm_source(self, source_path: Path, work_dir: Path) -> Path:
        if source_path.suffix.lower() in {".doc", ".ppt", ".pptx"}:
            return self._ensure_pdf(source_path, work_dir / "notebooklm_pdf")
        return source_path

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

    def _ensure_pdf(self, source: Path, work_dir: Path) -> Path:
        if source.suffix.lower() == ".pdf":
            return source

        converter = self._find_office_converter()
        if not converter:
            raise RuntimeError(
                "旧版按页合成需要先把 Word/PPT 转成 PDF，但当前系统没有找到 LibreOffice/soffice。"
                "请安装 LibreOffice，或改用“AI解读生成视频”模式。"
            )

        out_dir = work_dir / "converted_pdf"
        out_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                converter,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(source),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        candidates = sorted(out_dir.glob(f"{source.stem}*.pdf")) or sorted(out_dir.glob("*.pdf"))
        if not candidates:
            raise RuntimeError(f"Word/PPT 转 PDF 失败：没有生成 PDF 文件（{source.name}）")
        return candidates[0]

    def _find_office_converter(self) -> str:
        for command in ("soffice", "libreoffice"):
            found = shutil.which(command)
            if found:
                return found

        mac_candidates = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/Applications/OpenOffice.app/Contents/MacOS/soffice",
        ]
        for candidate in mac_candidates:
            if Path(candidate).exists():
                return candidate
        return ""

    def _extract_document_page_texts(self, source: Path) -> list[str]:
        text = extract_text_from_document(source, max_chars=18000)
        suffix = source.suffix.lower()
        if suffix in {".ppt", ".pptx"}:
            slide_blocks = [
                block.strip()
                for block in text.splitlines()
                if block.strip()
            ]
            if slide_blocks:
                return slide_blocks

        paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
        chunks = []
        current = ""
        for paragraph in paragraphs:
            if current and len(current) + len(paragraph) > 900:
                chunks.append(current)
                current = paragraph
            else:
                current = f"{current}\n{paragraph}".strip()
        if current:
            chunks.append(current)
        return chunks or [text]

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

    async def _build_narrations(self, page_texts: list[str], title: str) -> list[str]:
        narrations = []
        total = len(page_texts)
        for idx, text in enumerate(page_texts, start=1):
            if self.core.llm and self.core.config.get("llm", {}).get("api_key"):
                prompt = (
                    "请根据绘本 PDF 的 OCR 页面文字，为这一页生成一段适合儿童绘本视频的中文旁白。"
                    "要求：自然、温柔、口语化，适合直接朗读；不要解释 OCR，不要说“这一页”；"
                    "不要加入舞台说明；长度控制在 1 到 2 句，约 20 到 45 个汉字。"
                    f"\n书名：{title}\n页码：{idx}/{total}\nOCR文字：{text or '这一页主要是插图，文字很少或没有识别到。'}"
                )
                try:
                    out = await self.core.llm(prompt, temperature=0.65, max_tokens=180)
                    narration = self._clean_narration(str(out))
                    if narration:
                        narrations.append(narration)
                        continue
                except Exception as exc:
                    logger.warning(f"LLM narration generation failed for page {idx}: {exc}")

            fallback = self._clean_narration(text)
            narrations.append(fallback or f"画面里藏着故事的新线索，让我们一起看看第 {idx} 页发生了什么。")
        return narrations

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

    def _ensure_still_image(self, path: Path):
        """Ensure a media file is a real still image even if a workflow returned video bytes."""
        try:
            with Image.open(path) as image:
                image.verify()
            return
        except Exception:
            pass

        temp_out = path.with_suffix(".frame.png")
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(path),
                "-frames:v", "1",
                str(temp_out),
            ],
            check=True,
        )
        temp_out.replace(path)

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

    async def _make_generated_audio(
        self,
        narrations: list[str],
        out_dir: Path,
        speed: float,
        progress_callback: ProgressCallback = None,
    ) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_paths = []
        total = len(narrations)
        for idx, narration in enumerate(narrations, start=1):
            self._progress(progress_callback, f"生成自动旁白 {idx}/{total}", 0.74 + 0.06 * idx / max(total, 1))
            out = out_dir / f"page_{idx:03d}.mp3"
            audio_path = await self.core.tts(
                text=narration,
                output_path=str(out),
                speed=speed,
                index=idx,
            )
            final_audio_path = Path(audio_path) if audio_path else out
            if not final_audio_path.exists():
                raise RuntimeError(f"自动旁白生成失败：未找到音频文件 {final_audio_path}")
            audio_paths.append(final_audio_path)
        return audio_paths

    def _concat_audio(self, audio_paths: list[Path], out: Path):
        if not audio_paths:
            raise RuntimeError("No generated narration audio files")

        list_path = out.parent / "narration_audio_list.txt"
        list_path.write_text(
            "".join(f"file '{path.resolve()}'\n" for path in audio_paths),
            encoding="utf-8",
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(list_path),
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

    def _make_timing_plan_from_durations(self, captions: list[str], audio_paths: list[Path]) -> list[dict]:
        start = 0.0
        plan = []
        for idx, (caption, audio_path) in enumerate(zip(captions, audio_paths), start=1):
            page_duration = self._probe_duration(audio_path)
            plan.append({"page": idx, "start": start, "duration": page_duration, "caption": caption})
            start += page_duration
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

    def _clean_narration(self, text: str) -> str:
        cleaned = " ".join(str(text or "").strip().strip("\"'“”‘’").split())
        prefixes = ["旁白：", "旁白:", "Narration:", "narration:"]
        for prefix in prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        return cleaned

    def _safe_stem(self, value: str) -> str:
        safe = "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")
        return safe or "book"

    def _progress(self, callback: ProgressCallback, message: str, value: float):
        logger.info(f"[BookPDF] {value:.0%} {message}")
        if callback:
            callback(message, value)
