# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""风格化工坊：上传视频 → 滤镜（秒级）或 AI 重绘（≤60 秒素材）。"""

from __future__ import annotations

import time
from pathlib import Path

import streamlit as st

from morpheus_video_studio.services.restyle import (
    AI_RESTYLE_MAX_SECONDS,
    apply_filter_style,
    list_filter_styles,
    probe_video,
    run_ai_restyle,
)
from morpheus_video_studio.style_presets import list_image_style_presets

_UPLOAD_DIR = Path("temp/restyle_uploads")
_OUTPUT_DIR = Path("output/restyle")


def _save_uploads(uploaded_files) -> list[Path]:
    batch_dir = _UPLOAD_DIR / time.strftime("%Y%m%d_%H%M%S")
    batch_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for uploaded in uploaded_files:
        target = batch_dir / uploaded.name
        target.write_bytes(uploaded.getbuffer())
        paths.append(target)
    return paths


def render_restyle_workshop() -> None:
    st.markdown("**上传一个或一组视频，转成其他风格。**")
    uploaded_files = st.file_uploader(
        "选择视频文件",
        type=["mp4", "mov", "m4v", "webm", "mkv"],
        accept_multiple_files=True,
        key="restyle_uploads",
    )

    mode = st.radio(
        "风格化方式",
        ["filter", "ai"],
        format_func=lambda value: {
            "filter": "🎨 风格滤镜（秒级出片，任意长度）",
            "ai": f"🖌️ AI 重绘（整画面重画，限 {AI_RESTYLE_MAX_SECONDS:.0f} 秒内素材）",
        }[value],
        horizontal=True,
        key="restyle_mode",
    )

    if mode == "filter":
        styles = list_filter_styles()
        style_id = st.selectbox(
            "滤镜风格",
            [style["id"] for style in styles],
            format_func=lambda value: next(
                f"{s['label']} —— {s['description']}" for s in styles if s["id"] == value
            ),
            key="restyle_filter_style",
        )
    else:
        presets = list_image_style_presets()
        preset_id = st.selectbox(
            "重绘风格（与图像风格预设一致）",
            [preset["id"] for preset in presets],
            format_func=lambda value: next(
                f"{p['label']} —— {p['description']}" for p in presets if p["id"] == value
            ),
            key="restyle_ai_style",
        )
        denoise = st.slider(
            "重绘强度",
            min_value=0.35,
            max_value=0.8,
            value=0.6,
            step=0.05,
            help="越高越像全新画面，越低越贴近原片。0.5-0.65 通常最稳。",
            key="restyle_denoise",
        )
        st.caption("⏱️ 预期速度：30 秒素材约 10 分钟，60 秒约 20 分钟。生成期间请不要关闭页面。")

    if not uploaded_files:
        st.info("先上传视频，再选择风格。支持一次选择多个文件批量处理。")
        return

    preview_col, run_col = st.columns(2)

    with preview_col:
        if mode == "filter" and st.button("生成 3 秒预览小样", use_container_width=True, key="restyle_preview_btn"):
            saved = _save_uploads(uploaded_files[:1])
            with st.spinner("正在生成预览…"):
                preview_path = _OUTPUT_DIR / "previews" / f"preview_{int(time.time())}.mp4"
                try:
                    apply_filter_style(saved[0], style_id, preview_path, preview_seconds=3)
                    st.session_state["restyle_preview_path"] = str(preview_path)
                except Exception as exc:
                    st.error(f"预览失败：{exc}")

    preview_path = st.session_state.get("restyle_preview_path")
    if mode == "filter" and preview_path and Path(preview_path).exists():
        st.video(preview_path)

    with run_col:
        run_label = "批量导出" if mode == "filter" else "开始 AI 重绘"
        if st.button(run_label, type="primary", use_container_width=True, key="restyle_run_btn"):
            saved = _save_uploads(uploaded_files)
            batch_dir = _OUTPUT_DIR / time.strftime("%Y%m%d_%H%M%S")
            results: list[str] = []
            errors: list[str] = []
            progress = st.progress(0.0)
            status = st.empty()
            for index, source in enumerate(saved, start=1):
                status.info(f"处理中 ({index}/{len(saved)}): {source.name}")
                try:
                    if mode == "filter":
                        out = batch_dir / f"{source.stem}_{style_id}.mp4"
                        results.append(apply_filter_style(source, style_id, out))
                    else:
                        info = probe_video(source)
                        if info["duration"] > AI_RESTYLE_MAX_SECONDS + 0.5:
                            errors.append(
                                f"{source.name}: 超过 {AI_RESTYLE_MAX_SECONDS:.0f} 秒"
                                f"（{info['duration']:.0f} 秒），请先剪短或改用滤镜"
                            )
                            continue
                        preset = next(p for p in list_image_style_presets() if p["id"] == preset_id)
                        out = batch_dir / f"{source.stem}_{preset_id}.mp4"
                        results.append(
                            run_ai_restyle(
                                source,
                                preset["prompt_prefix"],
                                out,
                                denoise=float(st.session_state.get("restyle_denoise", 0.6)),
                                progress_callback=lambda msg: status.info(msg),
                            )
                        )
                except Exception as exc:
                    errors.append(f"{source.name}: {exc}")
                progress.progress(index / len(saved))

            status.empty()
            if results:
                st.success(f"完成 {len(results)} 个视频，输出目录：{batch_dir}")
                st.session_state["restyle_results"] = results
            for message in errors:
                st.error(message)

    for result in st.session_state.get("restyle_results", []):
        if Path(result).exists():
            st.video(result)
            with open(result, "rb") as handle:
                st.download_button(
                    f"下载 {Path(result).name}",
                    handle.read(),
                    file_name=Path(result).name,
                    mime="video/mp4",
                    key=f"restyle_download_{Path(result).name}",
                )
