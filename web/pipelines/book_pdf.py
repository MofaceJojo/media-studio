# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""
Picture book PDF pipeline UI.
"""

import os
import time
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
from loguru import logger

from morpheus_video_studio.config import config_manager
from morpheus_video_studio.pipelines.book_pdf import BookPDFVideoPipeline
from web.pipelines.base import PipelineUI, register_pipeline_ui
from web.utils.async_helpers import run_async


class BookPDFPipelineUI(PipelineUI):
    name = "book_pdf_video"
    display_name = "绘本PDF自动视频"
    icon = "📖"
    description = "上传 PDF/图片书页和音频，自动拆页、OCR、重绘插图、加字幕并合成视频。"

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
            pdf_file = st.file_uploader(
                "PDF 文件",
                type=["pdf"],
                key="book_pdf_upload",
                help="一本绘本或一组排好页序的 PDF。",
            )
            audio_file = st.file_uploader(
                "旁白音频",
                type=["mp3", "wav", "m4a", "aac"],
                key="book_audio_upload",
                help="成片会以这个音频长度自动分配每页时长。",
            )
            title = st.text_input("视频标题", value="Picture Book Video", key="book_pdf_title")

        paths = {"pdf_path": None, "audio_path": None, "title": title}
        if pdf_file and audio_file:
            upload_dir = Path("temp/book_pdf_uploads") / st.session_state.get(
                "book_pdf_upload_id", uuid.uuid4().hex[:12]
            )
            st.session_state.book_pdf_upload_id = upload_dir.name
            upload_dir.mkdir(parents=True, exist_ok=True)

            pdf_path = upload_dir / pdf_file.name
            audio_path = upload_dir / audio_file.name
            pdf_path.write_bytes(pdf_file.getbuffer())
            audio_path.write_bytes(audio_file.getbuffer())
            paths["pdf_path"] = str(pdf_path.resolve())
            paths["audio_path"] = str(audio_path.resolve())
            st.success("文件已准备好")

        return paths

    def _render_options(self) -> dict:
        with st.container(border=True):
            st.markdown("**生成设置**")
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
            )
            height = st.select_slider(
                "重绘高度",
                options=[512, 768, 1024, 1280],
                value=768,
                key="book_pdf_height",
            )
            steps = st.slider("重绘步数", min_value=4, max_value=30, value=18, step=1)
            denoise = st.slider("参考原图强度", min_value=0.35, max_value=0.90, value=0.68, step=0.01)
            cfg = st.slider("提示词权重", min_value=3.0, max_value=12.0, value=7.0, step=0.5)
            speed = st.slider("旁白加速", min_value=1.0, max_value=1.5, value=1.12, step=0.01)

        with st.container(border=True):
            st.markdown("**输出路径**")
            output_dir = st.text_input(
                "成片目录",
                value="/Volumes/MACDATA/成片/Morpheus Video Studio自动绘本视频",
                key="book_pdf_output_dir",
            )

        return {
            "redraw_pages": redraw_pages,
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

            ready = bool(params.get("pdf_path") and params.get("audio_path"))
            if not ready:
                st.info("先上传 PDF 和旁白音频。")

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
                    stem = Path(params["pdf_path"]).stem.replace(" ", "_")
                    output_path = output_dir / f"{stem}_自动重绘字幕版.mp4"

                    pipeline = BookPDFVideoPipeline(morpheus_video_studio)
                    result = run_async(
                        pipeline(
                            pdf_path=params["pdf_path"],
                            audio_path=params["audio_path"],
                            output_path=str(output_path),
                            title=params["title"] or stem,
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
