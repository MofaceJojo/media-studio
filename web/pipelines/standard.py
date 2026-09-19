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

"""
Standard Pipeline UI

Implements the classic 3-column layout for the Standard Pipeline.
"""

from typing import Any

import streamlit as st

# Import components
from web.components.content_input import render_bgm_section, render_content_input
from web.components.video_generation_config import render_video_generation_config
from web.components.output_preview import render_output_preview
from web.components.style_config import render_style_config
from web.i18n import tr
from web.pipelines.base import PipelineUI, register_pipeline_ui


class StandardPipelineUI(PipelineUI):
    """
    UI for the Standard Video Generation Pipeline.
    Implements the classic 3-column layout.
    """
    name = "quick_create"
    icon = "⚡"
    
    @property
    def display_name(self):
        return tr("pipeline.quick_create.name")
    
    @property
    def description(self):
        return tr("pipeline.quick_create.description")
    
    def render(self, morpheus_video_studio: Any):
        # Quick-create is video-first. Pre-seed the template picker on first load
        # so users don't accidentally generate static image slideshows.
        if not st.session_state.get("quick_create_template_defaults_initialized"):
            st.session_state["template_type_selector"] = "video"
            st.session_state.pop("selected_template", None)
            st.session_state.pop("last_template_type", None)
            st.session_state["quick_create_template_defaults_initialized"] = True

        content_tab, visual_tab, audio_tab = st.tabs(
            ["1. 文案与生成", "2. 画面与素材", "3. 声音与字幕"]
        )

        with content_tab:
            input_col, output_col = st.columns([1.15, 0.85], gap="large")
            with input_col:
                content_params = render_content_input(morpheus_video_studio)
            with output_col:
                output_slot = st.container()

        with audio_tab:
            voice_col, subtitle_col = st.columns(2, gap="large")
            with voice_col:
                tts_slot = st.container()
                bgm_params = render_bgm_section(key_prefix="quick_")
            with subtitle_col:
                subtitle_slot = st.container()

        with visual_tab:
            st.caption("先设置视频素材与画幅，再选择分镜模板和媒体生成策略。")
            video_slot = st.container()
            style_params = render_style_config(morpheus_video_studio, tts_container=tts_slot)

        video_generation_params = render_video_generation_config(
            style_params,
            video_container=video_slot,
            subtitle_container=subtitle_slot,
        )

        video_params = {
            "pipeline": self.name,
            **content_params,
            **bgm_params,
            **style_params,
            **video_generation_params,
        }

        if video_params.get("video_count", 1) > 1 and not video_params.get("batch_mode"):
            video_params["batch_mode"] = True
            video_params["topics"] = [video_params.get("text", "")] * video_params["video_count"]

        with output_slot:
            render_output_preview(morpheus_video_studio, video_params)


# Register self
register_pipeline_ui(StandardPipelineUI)
