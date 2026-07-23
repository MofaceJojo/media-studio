from __future__ import annotations

from typing import Any

import streamlit as st

from morpheus_video_studio.services.stock_publish_tools import merge_media
from web.pipelines.base import PipelineUI, register_pipeline_ui
from web.pipelines.video_mix import _size_from_layout


class VideoMergePipelineUI(PipelineUI):
    name = "video_merge"
    display_name = "合并视频"
    icon = "🧩"
    description = "按顺序合并本地图片/视频片段，可统一画幅、帧率并添加背景音乐。"

    def render(self, morpheus_video_studio: Any):
        left, right = st.columns([1, 1])
        with left:
            with st.container(border=True):
                st.markdown("**合并素材**")
                raw_files = st.text_area(
                    "文件路径",
                    placeholder="/Users/you/Videos/a.mp4\n/Users/you/Pictures/b.png",
                    height=220,
                    key="merge_files",
                )
                output_name = st.text_input("输出文件名", value="merged-video.mp4", key="merge_output_name")

            with st.container(border=True):
                st.markdown("**合成参数**")
                layout = st.selectbox("画幅", ["9:16", "16:9", "1:1"], key="merge_layout")
                fps = st.selectbox("帧率", [20, 25, 30], index=2, key="merge_fps")
                clip_duration = st.slider("图片/片段时长", 2.0, 12.0, 5.0, 0.5, key="merge_clip_duration")
                bgm_path = st.text_input("背景音乐文件", key="merge_bgm_path")
                bgm_volume = st.slider("背景音乐音量", 0.0, 1.0, 0.25, 0.05, key="merge_bgm_volume")

        with right:
            with st.container(border=True):
                st.markdown("**输出预览**")
                if st.button("合并视频", type="primary", use_container_width=True):
                    try:
                        files = [line.strip() for line in raw_files.splitlines() if line.strip()]
                        with st.spinner("正在合并..."):
                            output = merge_media(
                                files,
                                output_name=output_name,
                                size=_size_from_layout(layout),
                                fps=fps,
                                clip_duration=clip_duration,
                                bgm_path=bgm_path,
                                bgm_volume=bgm_volume,
                            )
                        st.session_state["merge_output"] = str(output)
                    except Exception as exc:
                        st.error(str(exc))

                output = st.session_state.get("merge_output")
                if output:
                    st.success(output)
                    st.video(output)


register_pipeline_ui(VideoMergePipelineUI)
