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
Style configuration components for web UI (middle column)
"""

import os
from pathlib import Path

import streamlit as st
from loguru import logger

from web.i18n import tr, get_language
from web.utils.async_helpers import run_async
from web.components.tts_preferences import (
    get_local_tts_preferences,
    get_omnivoice_tts_preferences,
    persist_local_tts_preferences,
    persist_omnivoice_tts_preferences,
)
from morpheus_video_studio.config import config_manager
from morpheus_video_studio.utils.omnivoice_util import (
    check_omnivoice_health,
    fetch_omnivoice_catalog,
    format_omnivoice_error,
    normalize_omnivoice_instruct,
)


def render_style_config(morpheus_video_studio):
    """Render style configuration section (middle column)"""
    # TTS Section (moved from left column)
    # ====================================================================
    with st.container(border=True):
        st.markdown(f"**{tr('section.tts')}**")
        
        with st.expander(tr("help.feature_description"), expanded=False):
            st.markdown(f"**{tr('help.what')}**")
            st.markdown(tr("tts.what"))
            st.markdown(f"**{tr('help.how')}**")
            st.markdown(tr("tts.how"))
        
        # Get TTS config
        comfyui_config = config_manager.get_comfyui_config()
        tts_config = comfyui_config["tts"]
        
        # Inference mode selection
        tts_mode = st.radio(
            tr("tts.inference_mode"),
            ["local", "omnivoice", "comfyui"],
            horizontal=True,
            format_func=lambda x: tr(f"tts.mode.{x}") if x != "omnivoice" else "OmniVoice 本地",
            index={"local": 0, "omnivoice": 1, "comfyui": 2}.get(tts_config.get("inference_mode", "local"), 0),
            key="digital_tts_inference_mode"
        )
        
        # Show hint based on mode
        if tts_mode == "omnivoice":
            st.caption("数字人口播会直接调用你电脑上的 OmniVoice Studio，可复用音频工坊里保存的音色。")
        elif tts_mode == "local":
            st.caption(tr("tts.mode.local_hint"))
        else:
            st.caption(tr("tts.mode.comfyui_hint"))
        
        # ================================================================
        # Local Mode UI
        # ================================================================
        if tts_mode == "local":
            # Import voice configuration
            from morpheus_video_studio.tts_voices import EDGE_TTS_VOICES, get_voice_display_name
            
            # Get saved voice from config
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
                
                # Set default index if matches saved voice
                if voice_id == saved_voice:
                    default_voice_index = idx
            
            # Two-column layout: Voice | Speed
            voice_col, speed_col = st.columns([1, 1])
            
            with voice_col:
                # Voice selector
                selected_voice_display = st.selectbox(
                    tr("tts.voice_selector"),
                    voice_options,
                    index=default_voice_index,
                    key="digital_tts_local_voice"
                )
                
                # Get actual voice ID
                selected_voice_index = voice_options.index(selected_voice_display)
                selected_voice = voice_ids[selected_voice_index]
            
            with speed_col:
                # Speed slider
                tts_speed = st.slider(
                    tr("tts.speed"),
                    min_value=0.5,
                    max_value=2.0,
                    value=saved_speed,
                    step=0.1,
                    format="%.1fx",
                    key="digital_tts_local_speed"
                )
                st.caption(tr("tts.speed_label", speed=f"{tts_speed:.1f}"))

            persist_local_tts_preferences(selected_voice, tts_speed)
            
            # Variables for video generation
            tts_workflow_key = None
            ref_audio_path = None
        
        # ================================================================
        # OmniVoice Mode UI
        # ================================================================
        elif tts_mode == "omnivoice":
            omni_config = tts_config.get("omnivoice", {})
            omni_base_url = omni_config.get("base_url", "http://127.0.0.1:3900").rstrip("/")
            saved_voice, saved_speed, _, saved_instruct = get_omnivoice_tts_preferences(
                omni_config.get("voice", "default"),
                float(omni_config.get("speed", 1.0)),
                omni_config.get("model", "omnivoice"),
                normalize_omnivoice_instruct(omni_config.get("instruct")) or "男，青年",
            )
            preferred_voice = st.session_state.get("studio_audio_preferred_omni_voice")

            omni_ok, omni_status = check_omnivoice_health(omni_base_url)
            if omni_ok:
                st.success(omni_status)
            else:
                st.warning(omni_status)

            test_col, _ = st.columns([1, 3])
            with test_col:
                if st.button("测试 OmniVoice", key="digital_test_omnivoice_btn", use_container_width=True):
                    ok, msg = check_omnivoice_health(omni_base_url, timeout=5.0)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

            voice_items = []
            voice_lookup: dict[str, dict] = {}
            if omni_ok:
                try:
                    voice_items = fetch_omnivoice_catalog(omni_base_url, timeout=3.0).get("voices", [])
                except Exception:
                    voice_items = []

            voice_ids = []
            voice_labels = []
            for item in voice_items:
                voice_id = item.get("voice_id")
                if not voice_id:
                    continue
                voice_lookup[voice_id] = item
                voice_ids.append(voice_id)
                meta = " · ".join(
                    value for value in [
                        item.get("type"),
                        item.get("language"),
                    ] if value
                )
                label = item.get("name") or voice_id
                voice_labels.append(f"{label} ({voice_id})" + (f" · {meta}" if meta else ""))

            if not voice_ids:
                voice_ids = ["default", "alloy", "nova", "demo0001"]
                voice_labels = ["Default", "Alloy", "Nova", "OmniVoice Demo"]
            elif saved_voice not in voice_ids:
                voice_ids.append(saved_voice)
                voice_labels.append(f"{saved_voice} (当前配置)")

            default_voice_index = voice_ids.index(saved_voice) if saved_voice in voice_ids else 0
            if preferred_voice and preferred_voice in voice_ids:
                default_voice_index = voice_ids.index(preferred_voice)

            voice_col, speed_col = st.columns([1, 1])
            with voice_col:
                selected_voice_display = st.selectbox(
                    tr("tts.voice_selector"),
                    voice_labels,
                    index=default_voice_index,
                    key="digital_tts_omnivoice_voice_v2",
                )
                selected_voice = voice_ids[voice_labels.index(selected_voice_display)]
            with speed_col:
                tts_speed = st.slider(
                    tr("tts.speed"),
                    min_value=0.5,
                    max_value=2.0,
                    value=saved_speed,
                    step=0.1,
                    format="%.1fx",
                    key="digital_tts_omnivoice_speed_v2",
                )
                st.caption(tr("tts.speed_label", speed=f"{tts_speed:.1f}"))

            if preferred_voice and preferred_voice == selected_voice:
                st.caption(f"已复用音频工坊默认音色：`{selected_voice}`")
            selected_voice_meta = voice_lookup.get(selected_voice)
            if selected_voice_meta:
                st.caption(
                    " · ".join(
                        value for value in [
                            selected_voice_meta.get("type"),
                            selected_voice_meta.get("language"),
                            selected_voice_meta.get("description"),
                        ] if value
                    )
                )

            omnivoice_instruct = st.text_input(
                "OmniVoice 风格指令",
                value=saved_instruct,
                key="digital_tts_omnivoice_instruct_v2",
                help="仅支持短标签，例如：男，青年 / female, young adult。不要写长句。",
            )
            omnivoice_instruct = normalize_omnivoice_instruct(omnivoice_instruct) or "男，青年"
            persist_omnivoice_tts_preferences(
                selected_voice,
                tts_speed,
                instruct=omnivoice_instruct,
            )
            tts_workflow_key = None
            ref_audio_path = None

        # ================================================================
        # ComfyUI Mode UI
        # ================================================================
        else:  # comfyui mode
            tts_workflow_key = "selfhost/tts_edge.json"
            selected_audio_asset = st.session_state.get("studio_selected_audio_asset_path")
            selected_audio_path = (
                str(Path(selected_audio_asset).resolve())
                if selected_audio_asset and Path(selected_audio_asset).exists()
                else None
            )
            
            # Reference audio upload (optional, for voice cloning)
            ref_audio_file = st.file_uploader(
                tr("tts.ref_audio"),
                type=["mp3", "wav", "flac", "m4a", "aac", "ogg"],
                help=tr("tts.ref_audio_help"),
                key="digital_ref_audio_upload"
            )
            
            # Save uploaded ref_audio to temp file if provided
            ref_audio_path = None
            if ref_audio_file is not None:
                # Audio preview player (directly play uploaded file)
                st.audio(ref_audio_file)
                
                # Save to temp directory
                temp_dir = Path("temp")
                temp_dir.mkdir(exist_ok=True)
                ref_audio_path = temp_dir / f"ref_audio_{ref_audio_file.name}"
                with open(ref_audio_path, "wb") as f:
                    f.write(ref_audio_file.getbuffer())
            elif selected_audio_path:
                ref_audio_path = Path(selected_audio_path)
                st.info(f"已从资产库带入声音参考：{Path(selected_audio_path).name}")
                st.audio(selected_audio_path)
            
            # Variables for video generation
            selected_voice = None
            tts_speed = None
        
        # ================================================================
        # TTS Preview (works for both modes)
        # ================================================================
        with st.expander(tr("tts.preview_title"), expanded=False):
            # Preview text input
            preview_text = st.text_input(
                tr("tts.preview_text"),
                value="大家好，这是一段测试语音。",
                placeholder=tr("tts.preview_text_placeholder"),
                key="digital_tts_preview_text"
            )
            
            # Preview button
            if st.button(tr("tts.preview_button"), key="gidital_preview_tts", use_container_width=True):
                with st.spinner(tr("tts.previewing")):
                    try:
                        # Build TTS params based on mode
                        tts_params = {
                            "text": preview_text,
                            "inference_mode": tts_mode
                        }
                        
                        if tts_mode == "local":
                            tts_params["voice"] = selected_voice
                            tts_params["speed"] = tts_speed
                        elif tts_mode == "omnivoice":
                            tts_params["voice"] = selected_voice
                            tts_params["speed"] = tts_speed
                            tts_params["instruct"] = omnivoice_instruct
                        else:  # comfyui
                            tts_params["workflow"] = tts_workflow_key
                            if ref_audio_path:
                                tts_params["ref_audio"] = str(ref_audio_path)
                        
                        audio_path = run_async(morpheus_video_studio.tts(**tts_params))
                        
                        # Play the audio
                        if audio_path:
                            st.success(tr("tts.preview_success"))
                            if os.path.exists(audio_path):
                                st.audio(audio_path)
                            elif audio_path.startswith('http'):
                                st.audio(audio_path)
                            else:
                                st.error("Failed to generate preview audio")
                            
                            # Show file path
                            st.caption(f"📁 {audio_path}")
                        else:
                            st.error("Failed to generate preview audio")
                    except Exception as e:
                        err = format_omnivoice_error(e) if tts_mode == "omnivoice" else str(e)
                        st.error(tr("tts.preview_failed", error=err))
                        logger.exception(e)
    
    # Return all style configuration parameters
    return {
        "tts_inference_mode": tts_mode,
        "tts_voice": selected_voice if tts_mode in ("local", "omnivoice") else None,
        "tts_speed": tts_speed if tts_mode in ("local", "omnivoice") else None,
        "tts_instruct": omnivoice_instruct if tts_mode == "omnivoice" else None,
        "tts_workflow": tts_workflow_key if tts_mode == "comfyui" else None,
        "ref_audio": str(ref_audio_path) if ref_audio_path else None,
    }
