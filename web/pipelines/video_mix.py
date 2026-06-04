from __future__ import annotations

from typing import Any

import streamlit as st

from morpheus_video_studio.services.moneyprinter_tools import media_files, mix_from_scene_dirs
from web.pipelines.base import PipelineUI, register_pipeline_ui


def _size_from_layout(layout: str) -> tuple[int, int]:
    if layout == "16:9":
        return 1920, 1080
    if layout == "1:1":
        return 1080, 1080
    return 1080, 1920


class VideoMixPipelineUI(PipelineUI):
    name = "video_mix"
    display_name = "视频混剪区"
    icon = "🎛️"
    description = "从多个场景素材文件夹随机抽取片段，批量生成不重复短视频。"

    def render(self, morpheus_video_studio: Any):
        left, middle, right = st.columns([1, 1, 1])
        with left:
            with st.container(border=True):
                st.markdown("**场景素材**")
                scene_count = st.slider("场景数量", 1, 5, 3, key="mix_scene_count")
                scene_dirs = []
                for index in range(scene_count):
                    value = st.text_input(f"场景 {index + 1} 素材文件夹", key=f"mix_scene_dir_{index}")
                    scene_dirs.append(value)
                    count = len(media_files(value)) if value else 0
                    st.caption(f"可用素材：{count}")

        with middle:
            with st.container(border=True):
                st.markdown("**混剪参数**")
                layout = st.selectbox("画幅", ["9:16", "16:9", "1:1"], key="mix_layout")
                fps = st.selectbox("帧率", [20, 25, 30], index=2, key="mix_fps")
                clip_duration = st.slider("单段时长", 2.0, 12.0, 5.0, 0.5, key="mix_clip_duration")
                count = st.slider("生成数量", 1, 20, 1, key="mix_count")
                bgm_path = st.text_input("背景音乐文件", key="mix_bgm_path")
                bgm_volume = st.slider("背景音乐音量", 0.0, 1.0, 0.25, 0.05, key="mix_bgm_volume")

        with right:
            with st.container(border=True):
                st.markdown("**输出**")
                if st.button("开始混剪", type="primary", use_container_width=True):
                    try:
                        with st.spinner("正在混剪..."):
                            outputs = mix_from_scene_dirs(
                                scene_dirs,
                                count=count,
                                size=_size_from_layout(layout),
                                fps=fps,
                                clip_duration=clip_duration,
                                bgm_path=bgm_path,
                                bgm_volume=bgm_volume,
                            )
                        st.session_state["mix_outputs"] = [str(path) for path in outputs]
                    except Exception as exc:
                        st.error(str(exc))

                for path in st.session_state.get("mix_outputs", []):
                    st.success(path)
                    st.video(path)


register_pipeline_ui(VideoMixPipelineUI)
