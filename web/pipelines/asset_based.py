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
Asset-Based Pipeline UI

Implements the UI for generating videos from user-provided assets.
"""

import os
import time
from pathlib import Path
from typing import Any

import streamlit as st
from loguru import logger

from web.i18n import tr, get_language
from web.components.tts_preferences import (
    get_local_tts_preferences,
    persist_local_tts_preferences,
)
from web.pipelines.base import PipelineUI, register_pipeline_ui
from web.components.content_input import render_bgm_section
from web.utils.async_helpers import run_async
from web.utils.streamlit_helpers import check_and_warn_selfhost_workflow
from morpheus_video_studio.config import config_manager
from morpheus_video_studio.models.progress import ProgressEvent


class AssetBasedPipelineUI(PipelineUI):
    """
    UI for the Asset-Based Video Generation Pipeline.
    Generates videos from user-provided assets (images/videos).
    """
    name = "custom_media"
    icon = "🎨"
    
    @property
    def display_name(self):
        return tr("pipeline.custom_media.name")
    
    @property
    def description(self):
        return tr("pipeline.custom_media.description")
    
    def render(self, morpheus_video_studio: Any):
        # Three-column layout
        left_col, middle_col, right_col = st.columns([1, 1, 1])
        
        # ====================================================================
        # Left Column: Asset Upload & Video Info
        # ====================================================================
        with left_col:
            asset_params = self._render_asset_input()
            bgm_params = render_bgm_section(key_prefix="asset_")
        
        # ====================================================================
        # Middle Column: Video Configuration
        # ====================================================================
        with middle_col:
            config_params = self._render_video_config(morpheus_video_studio)
        
        # ====================================================================
        # Right Column: Output Preview
        # ====================================================================
        with right_col:
            # Combine all parameters
            video_params = {
                "pipeline": self.name,
                **asset_params,
                **bgm_params,
                **config_params
            }
            
            self._render_output_preview(morpheus_video_studio, video_params)
    
    def _render_asset_input(self) -> dict:
        """Render asset upload section"""
        with st.container(border=True):
            st.markdown(f"**{tr('asset_based.section.assets')}**")
            
            with st.expander(tr("help.feature_description"), expanded=False):
                st.markdown(f"**{tr('help.what')}**")
                st.markdown(tr("asset_based.assets.what"))
                st.markdown(f"**{tr('help.how')}**")
                st.markdown(tr("asset_based.assets.how"))
            
            preloaded_assets = st.session_state.get("studio_selected_asset_paths") or []
            valid_preloaded_assets = [
                str(Path(path).resolve())
                for path in preloaded_assets
                if path and Path(path).exists()
            ]
            if valid_preloaded_assets:
                st.info(f"已从资产库带入 {len(valid_preloaded_assets)} 个素材，可直接生成或继续补充上传。")

            # File uploader for multiple files
            uploaded_files = st.file_uploader(
                tr("asset_based.assets.upload"),
                type=["jpg", "jpeg", "png", "gif", "webp", "mp4", "mov", "avi", "mkv", "webm"],
                accept_multiple_files=True,
                help=tr("asset_based.assets.upload_help"),
                key="asset_files"
            )
            
            # Save uploaded files to temp directory with unique session ID
            asset_paths = list(valid_preloaded_assets)
            if uploaded_files:
                import uuid
                session_id = str(uuid.uuid4()).replace('-', '')[:12]
                temp_dir = Path(f"temp/assets_{session_id}")
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                for uploaded_file in uploaded_files:
                    file_path = temp_dir / uploaded_file.name
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    asset_paths.append(str(file_path.absolute()))

            if asset_paths:
                st.success(tr("asset_based.assets.count", count=len(asset_paths)))

                with st.expander(tr("asset_based.assets.preview"), expanded=True):
                    cols = st.columns(3)

                    preview_items: list[tuple[str, str, str]] = []
                    for path in valid_preloaded_assets:
                        preview_items.append((Path(path).name, path, "preloaded"))
                    for path in asset_paths:
                        if path not in valid_preloaded_assets:
                            preview_items.append((Path(path).name, path, "uploaded"))

                    for i, (label, path, source_kind) in enumerate(preview_items):
                        with cols[i % 3]:
                            ext = Path(path).suffix.lower()
                            caption = f"{label} · 资产库" if source_kind == "preloaded" else label
                            if ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                                st.image(path, caption=caption, use_container_width=True)
                            elif ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
                                st.video(path)
                                st.caption(caption)
            else:
                st.info(tr("asset_based.assets.empty_hint"))
        
        # Video title & intent
        with st.container(border=True):
            st.markdown(f"**{tr('asset_based.section.video_info')}**")
            
            video_title = st.text_input(
                tr("asset_based.video_title"),
                placeholder=tr("asset_based.video_title_placeholder"),
                help=tr("asset_based.video_title_help"),
                key="asset_video_title"
            )
            
            intent = st.text_area(
                tr("asset_based.intent"),
                placeholder=tr("asset_based.intent_placeholder"),
                help=tr("asset_based.intent_help"),
                height=100,
                key="asset_intent"
            )
        
        return {
            "assets": asset_paths,
            "video_title": video_title,
            "intent": intent if intent else None
        }
    
    def _render_video_config(self, morpheus_video_studio: Any) -> dict:
        """Render video configuration section"""
        # Duration configuration
        with st.container(border=True):
            st.markdown(f"**{tr('video.title')}**")
            
            # Duration slider
            duration = st.slider(
                tr("asset_based.duration"),
                min_value=15,
                max_value=120,
                value=30,
                step=5,
                help=tr("asset_based.duration_help"),
                key="asset_duration"
            )
            st.caption(tr("asset_based.duration_label", seconds=duration))
        
        # Workflow source selection
        with st.container(border=True):
            st.markdown(f"**{tr('asset_based.section.source')}**")
            
            with st.expander(tr("help.feature_description"), expanded=False):
                st.markdown(f"**{tr('help.what')}**")
                st.markdown(tr("asset_based.source.what"))
                st.markdown(f"**{tr('help.how')}**")
                st.markdown(tr("asset_based.source.how"))
            
            source_options = {"selfhost": tr("asset_based.source.selfhost")}
            
            comfyui_config = config_manager.get_comfyui_config()
            has_selfhost = bool(comfyui_config.get("comfyui_url"))
            
            default_source_index = 0
            
            source = st.radio(
                tr("asset_based.source.select"),
                options=list(source_options.keys()),
                format_func=lambda x: source_options[x],
                index=default_source_index,
                horizontal=True,
                key="asset_source",
                label_visibility="collapsed"
            )
            
            if not has_selfhost:
                st.warning(tr("asset_based.source.selfhost_not_configured"))
            else:
                st.info(tr("asset_based.source.selfhost_hint"))
                check_and_warn_selfhost_workflow("selfhost/analyse_image.json")
        
        # TTS configuration
        with st.container(border=True):
            st.markdown(f"**{tr('section.tts')}**")
            
            # Import voice configuration
            from morpheus_video_studio.tts_voices import EDGE_TTS_VOICES, get_voice_display_name
            
            # Get saved voice from config
            comfyui_config = config_manager.get_comfyui_config()
            tts_config = comfyui_config.get("tts", {})
            local_config = tts_config.get("local", {})
            saved_voice, saved_speed = get_local_tts_preferences(
                local_config.get("voice", "zh-CN-YunjianNeural"),
                float(local_config.get("speed", 1.2)),
            )
            
            # Build voice options with i18n
            voice_options = []
            voice_ids = []
            default_voice_index = 0
            
            for idx, voice_config in enumerate(EDGE_TTS_VOICES):
                voice_id = voice_config["id"]
                display_name = get_voice_display_name(voice_id, tr, get_language())
                voice_options.append(display_name)
                voice_ids.append(voice_id)
                
                if voice_id == saved_voice:
                    default_voice_index = idx
            
            # Two-column layout
            voice_col, speed_col = st.columns([1, 1])
            
            with voice_col:
                selected_voice_display = st.selectbox(
                    tr("tts.voice_selector"),
                    voice_options,
                    index=default_voice_index,
                    key="asset_tts_voice"
                )
                selected_voice_index = voice_options.index(selected_voice_display)
                voice_id = voice_ids[selected_voice_index]
            
            with speed_col:
                tts_speed = st.slider(
                    tr("tts.speed"),
                    min_value=0.5,
                    max_value=2.0,
                    value=saved_speed,
                    step=0.1,
                    format="%.1fx",
                    key="asset_tts_speed"
                )
                st.caption(tr("tts.speed_label", speed=f"{tts_speed:.1f}"))

            persist_local_tts_preferences(voice_id, tts_speed)
        
        return {
            "duration": duration,
            "source": source,
            "voice_id": voice_id,
            "tts_speed": tts_speed
        }
    
    def _render_output_preview(self, morpheus_video_studio: Any, video_params: dict):
        """Render output preview section"""
        with st.container(border=True):
            st.markdown(f"**{tr('section.video_generation')}**")
            
            # Check configuration
            if not config_manager.validate():
                st.warning(tr("settings.not_configured"))
            
            # Check if assets are provided
            assets = video_params.get("assets", [])
            if not assets:
                st.info(tr("asset_based.output.no_assets"))
                st.button(
                    tr("btn.generate"),
                    type="primary",
                    use_container_width=True,
                    disabled=True,
                    key="asset_generate_disabled"
                )
                return
            
            # Show asset summary
            st.info(tr("asset_based.output.ready", count=len(assets)))
            
            # Generate button
            if st.button(tr("btn.generate"), type="primary", use_container_width=True, key="asset_generate"):
                # Validate
                if not config_manager.validate():
                    st.error(tr("settings.not_configured"))
                    st.stop()
                
                # Show progress
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                start_time = time.time()
                
                try:
                    # Import pipeline
                    from morpheus_video_studio.pipelines.asset_based import AssetBasedPipeline
                    
                    # Create pipeline
                    pipeline = AssetBasedPipeline(morpheus_video_studio)
                    
                    # Progress callback
                    def update_progress(event: ProgressEvent):
                        if event.event_type == "analyzing_assets":
                            if event.extra_info == "start":
                                message = tr("asset_based.progress.analyzing_start", total=event.frame_total)
                            else:
                                message = tr("asset_based.progress.analyzing_complete", count=event.frame_total)
                        elif event.event_type == "analyzing_asset":
                            message = tr(
                                "asset_based.progress.analyzing_asset",
                                current=event.frame_current,
                                total=event.frame_total,
                                name=event.extra_info or ""
                            )
                        elif event.event_type == "generating_script":
                            if event.extra_info == "complete":
                                message = tr("asset_based.progress.script_complete")
                            else:
                                message = tr("asset_based.progress.generating_script")
                        elif event.event_type == "frame_step":
                            action_key = f"progress.step_{event.action}"
                            action_text = tr(action_key)
                            message = tr(
                                "progress.frame_step",
                                current=event.frame_current,
                                total=event.frame_total,
                                step=event.step,
                                action=action_text
                            )
                        elif event.event_type == "processing_frame":
                            message = tr(
                                "progress.frame",
                                current=event.frame_current,
                                total=event.frame_total
                            )
                        elif event.event_type == "concatenating":
                            if event.extra_info == "complete":
                                message = tr("asset_based.progress.concat_complete")
                            else:
                                message = tr("progress.concatenating")
                        elif event.event_type == "completed":
                            message = tr("progress.completed")
                        else:
                            message = tr(f"progress.{event.event_type}")
                        
                        status_text.text(message)
                        progress_bar.progress(min(int(event.progress * 100), 99))
                    
                    # Execute pipeline with progress callback
                    ctx = run_async(pipeline(
                        assets=video_params["assets"],
                        video_title=video_params.get("video_title", ""),
                        intent=video_params.get("intent"),
                        duration=video_params.get("duration", 30),
                        source=video_params.get("source", "selfhost"),
                        bgm_path=video_params.get("bgm_path"),
                        bgm_volume=video_params.get("bgm_volume", 0.2),
                        bgm_mode=video_params.get("bgm_mode", "loop"),
                        voice_id=video_params.get("voice_id", "zh-CN-YunjianNeural"),
                        tts_speed=video_params.get("tts_speed", 1.2),
                        progress_callback=update_progress
                    ))
                    
                    total_time = time.time() - start_time
                    
                    progress_bar.progress(100)
                    status_text.text(tr("status.success"))
                    
                    # Display result
                    st.success(tr("status.video_generated", path=ctx.final_video_path))
                    
                    st.markdown("---")
                    
                    # Video info
                    if os.path.exists(ctx.final_video_path):
                        file_size_mb = os.path.getsize(ctx.final_video_path) / (1024 * 1024)
                        n_scenes = len(ctx.storyboard.frames) if ctx.storyboard else 0
                        
                        info_text = (
                            f"⏱️ {tr('info.generation_time')} {total_time:.1f}s   "
                            f"📦 {file_size_mb:.2f}MB   "
                            f"🎬 {n_scenes}{tr('info.scenes_unit')}"
                        )
                        st.caption(info_text)
                        
                        st.markdown("---")
                        
                        # Video preview
                        st.video(ctx.final_video_path)
                        
                        # Download button
                        with open(ctx.final_video_path, "rb") as video_file:
                            video_bytes = video_file.read()
                            video_filename = os.path.basename(ctx.final_video_path)
                            st.download_button(
                                label="⬇️ 下载视频" if get_language() == "zh_CN" else "⬇️ Download Video",
                                data=video_bytes,
                                file_name=video_filename,
                                mime="video/mp4",
                                use_container_width=True
                            )
                    else:
                        st.error(tr("status.video_not_found", path=ctx.final_video_path))
                
                except Exception as e:
                    status_text.text("")
                    progress_bar.empty()
                    st.error(tr("status.error", error=str(e)))
                    logger.exception(e)
                    st.stop()


# Register self
register_pipeline_ui(AssetBasedPipelineUI)
