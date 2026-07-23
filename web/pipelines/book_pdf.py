# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""
Picture book PDF pipeline UI.
"""

import os
import time
import uuid
import importlib
from pathlib import Path
from typing import Any

import streamlit as st
from loguru import logger

from morpheus_video_studio.config import config_manager
from morpheus_video_studio.services.studio_library import StudioLibraryService
from web.pipelines.base import PipelineUI, register_pipeline_ui
from web.utils.async_helpers import run_async


class BookPDFPipelineUI(PipelineUI):
    name = "book_pdf_video"
    display_name = "绘本文档自动视频"
    icon = "📖"
    description = "上传 PDF、Word 或 PPT，AI 解读内容并生成短视频文案，再按文案自动生成视频。"

    def render(self, morpheus_video_studio: Any):
        left_col, middle_col, right_col = st.columns([1, 1, 1])

        with left_col:
            inputs = self._render_inputs()

        with middle_col:
            options = self._render_options()

        with right_col:
            self._render_run_panel(morpheus_video_studio, {**inputs, **options})

    def _render_inputs(self) -> dict:
        with st.container(border=True):
            st.markdown("**输入文件**")
            selected_item = None
            selected_content_id = st.session_state.get("studio_selected_content_id")
            if selected_content_id:
                selected_item = StudioLibraryService().get_content_item(selected_content_id)
            selected_source_path = selected_item.get("source_path") if selected_item else None
            selected_is_document = bool(
                selected_item
                and selected_item.get("source_kind") == "document"
                and selected_source_path
                and Path(selected_source_path).exists()
            )

            if selected_is_document:
                st.info(f"已从内容库带入文档：{selected_item.get('title') or Path(selected_source_path).stem}")

            document_file = st.file_uploader(
                "文档文件",
                type=["pdf", "docx", "doc", "pptx", "ppt"],
                key="book_pdf_upload",
                help="支持 PDF、Word（doc/docx）和 PPT（ppt/pptx）。AI 解读模式会直接提取文字；旧版按页合成会先转成 PDF。",
            )
            audio_file = st.file_uploader(
                "旁白音频（可选）",
                type=["mp3", "wav", "m4a", "aac"],
                key="book_audio_upload",
                help="AI 解读模式会根据文案重新合成旁白；这个入口仅保留给旧版按页合成模式。",
            )
            title = st.text_input(
                "视频标题",
                value=(selected_item.get("title") if selected_item else "Picture Book Video"),
                key="book_pdf_title",
            )

        paths = {"document_path": None, "audio_path": None, "title": title}
        if selected_is_document:
            paths["document_path"] = str(Path(selected_source_path).resolve())

        if document_file:
            upload_dir = Path("temp/book_pdf_uploads") / st.session_state.get(
                "book_pdf_upload_id", uuid.uuid4().hex[:12]
            )
            st.session_state.book_pdf_upload_id = upload_dir.name
            upload_dir.mkdir(parents=True, exist_ok=True)

            document_path = upload_dir / document_file.name
            document_path.write_bytes(document_file.getbuffer())
            paths["document_path"] = str(document_path.resolve())
            if audio_file:
                audio_path = upload_dir / audio_file.name
                audio_path.write_bytes(audio_file.getbuffer())
                paths["audio_path"] = str(audio_path.resolve())
                st.success("文档已准备好；音频仅在旧版按页模式使用")
            else:
                st.success("文档已准备好，将由 AI 解读内容并生成文案")
        elif selected_is_document:
            st.success("已使用内容库中的原始文档，无需重新上传。")

        return paths

    def _render_options(self) -> dict:
        with st.container(border=True):
            st.markdown("**生成设置**")
            content_mode_label = st.radio(
                "生成方式",
                ["AI解读生成视频", "旧版按页合成"],
                index=0,
                help="推荐使用 AI 解读生成视频：文档只作为内容来源，不直接使用页图或原文字幕。",
                key="book_pdf_content_mode",
            )
            content_mode = "ai_script" if content_mode_label == "AI解读生成视频" else "page_compose"
            analysis_backend_label = st.radio(
                "解读引擎",
                ["本地解读（默认）", "NotebookLM 解读（Beta）"],
                index=0,
                horizontal=True,
                disabled=content_mode != "ai_script",
                help="NotebookLM 只用于先把文档整理成结构化报告，再交给当前视频流水线生成短视频文案。",
                key="book_pdf_analysis_backend",
            )
            analysis_backend = "local" if analysis_backend_label == "本地解读（默认）" else "notebooklm"
            n_scenes = st.slider("视频分镜数", min_value=3, max_value=12, value=6, step=1)
            redraw_pages = False
            if content_mode == "page_compose":
                redraw_pages = st.checkbox("用 ComfyUI 重绘每页插图", value=True, key="book_pdf_redraw")
            max_pages_enabled = st.checkbox("只测试前几页", value=False, key="book_pdf_limit_enabled")
            max_pages = None
            if max_pages_enabled:
                max_pages = st.number_input("测试页数", min_value=1, max_value=20, value=2, step=1)

            width = st.select_slider(
                "重绘宽度",
                options=[512, 768, 1024, 1280],
                value=1024,
                key="book_pdf_width",
                disabled=content_mode == "ai_script",
            )
            height = st.select_slider(
                "重绘高度",
                options=[512, 768, 1024, 1280],
                value=768,
                key="book_pdf_height",
                disabled=content_mode == "ai_script",
            )
            steps = st.slider("重绘步数", min_value=4, max_value=30, value=18, step=1, disabled=content_mode == "ai_script")
            denoise = st.slider("参考原图强度", min_value=0.35, max_value=0.90, value=0.68, step=0.01, disabled=content_mode == "ai_script")
            cfg = st.slider("提示词权重", min_value=3.0, max_value=12.0, value=7.0, step=0.5, disabled=content_mode == "ai_script")
            speed = st.slider(
                "旁白语速",
                min_value=0.8,
                max_value=1.5,
                value=1.12,
                step=0.01,
                help="上传音频时会调整原旁白速度；未上传音频时会作为自动 TTS 的语速。",
            )

        with st.container(border=True):
            st.markdown("**输出路径**")
            output_dir = st.text_input(
                "成片目录",
                value="/Volumes/MACDATA/成片/Morpheus Video Studio自动绘本视频",
                key="book_pdf_output_dir",
            )

        return {
            "redraw_pages": redraw_pages,
            "content_mode": content_mode,
            "analysis_backend": analysis_backend,
            "n_scenes": int(n_scenes),
            "max_pages": int(max_pages) if max_pages else None,
            "width": int(width),
            "height": int(height),
            "steps": int(steps),
            "denoise": float(denoise),
            "cfg": float(cfg),
            "speed": float(speed),
            "output_dir": output_dir,
        }

    def _render_run_panel(self, morpheus_video_studio: Any, params: dict):
        with st.container(border=True):
            st.markdown("**自动执行**")
            if not config_manager.validate():
                st.warning("Morpheus Video Studio 的模型或 ComfyUI 配置还没通过校验。")

            ready = bool(params.get("document_path"))
            if not ready:
                st.info("先上传 PDF、Word 或 PPT；旁白音频可选。")
            elif not params.get("audio_path"):
                st.info("将由 AI 解读文档内容，生成短视频文案和旁白。")

            if st.button("开始自动生成", type="primary", use_container_width=True, disabled=not ready):
                if not config_manager.validate():
                    st.error("请先在上方配置好 LLM 和 ComfyUI。")
                    st.stop()

                progress_bar = st.progress(0)
                status_text = st.empty()
                start_time = time.time()

                def update_progress(message: str, value: float):
                    status_text.text(message)
                    progress_bar.progress(min(int(value * 100), 99))

                try:
                    output_dir = Path(params["output_dir"]).expanduser()
                    output_dir.mkdir(parents=True, exist_ok=True)
                    stem = Path(params["document_path"]).stem.replace(" ", "_")
                    output_path = output_dir / f"{stem}_自动重绘字幕版.mp4"

                    import morpheus_video_studio.pipelines.book_pdf as book_pdf_pipeline

                    book_pdf_pipeline = importlib.reload(book_pdf_pipeline)
                    pipeline = book_pdf_pipeline.BookPDFVideoPipeline(morpheus_video_studio)
                    result = run_async(
                        pipeline(
                            pdf_path=params["document_path"],
                            audio_path=params["audio_path"],
                            output_path=str(output_path),
                            title=params["title"] or stem,
                            content_mode=params["content_mode"],
                            analysis_backend=params["analysis_backend"],
                            n_scenes=params["n_scenes"],
                            width=params["width"],
                            height=params["height"],
                            steps=params["steps"],
                            denoise=params["denoise"],
                            cfg=params["cfg"],
                            speed=params["speed"],
                            max_pages=params["max_pages"],
                            redraw_pages=params["redraw_pages"],
                            progress_callback=update_progress,
                        )
                    )

                    progress_bar.progress(100)
                    status_text.text("完成")
                    elapsed = time.time() - start_time
                    st.success(f"自动流程完成：{result.output_path}")
                    st.caption(f"页数 {result.pages} | 时长 {result.duration:.1f}s | 用时 {elapsed:.1f}s")
                    if os.path.exists(result.output_path):
                        st.video(result.output_path)
                        with open(result.output_path, "rb") as video_file:
                            st.download_button(
                                "下载视频",
                                data=video_file.read(),
                                file_name=os.path.basename(result.output_path),
                                mime="video/mp4",
                                use_container_width=True,
                            )
                except Exception as exc:
                    status_text.text("")
                    progress_bar.empty()
                    st.error(f"自动流程失败：{exc}")
                    logger.exception(exc)
                    st.stop()


register_pipeline_ui(BookPDFPipelineUI)
