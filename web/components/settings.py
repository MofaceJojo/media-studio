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
System settings component for web UI
"""

import streamlit as st

from web.i18n import tr
from web.utils.async_helpers import run_async
from web.utils.streamlit_helpers import safe_rerun
from morpheus_video_studio.config import config_manager


def render_advanced_settings():
    """Render system configuration (required) with 2-column layout"""
    # Check if system is configured
    is_configured = config_manager.validate()
    
    # Expand if not configured, collapse if configured
    with st.expander(tr("settings.title"), expanded=not is_configured):
        # 2-column layout: LLM | ComfyUI, then full-width stock material settings.
        llm_col, comfyui_col = st.columns(2)
        
        # ====================================================================
        # Column 1: LLM Settings
        # ====================================================================
        with llm_col:
            with st.container(border=True):
                st.markdown(f"**{tr('settings.llm.title')}**")
                
                # Quick preset selection
                from morpheus_video_studio.llm_presets import get_preset_names, get_preset, find_preset_by_base_url_and_model
                
                # Custom at the end
                preset_names = get_preset_names() + ["Custom"]
                
                # Get current config
                current_llm = config_manager.get_llm_config()
                
                # Auto-detect which preset matches current config
                current_preset = find_preset_by_base_url_and_model(
                    current_llm["base_url"], 
                    current_llm["model"]
                )
                
                # Determine default index based on current config
                if current_preset:
                    # Current config matches a preset
                    default_index = preset_names.index(current_preset)
                else:
                    # Current config doesn't match any preset -> Custom
                    default_index = len(preset_names) - 1
                
                selected_preset = st.selectbox(
                    tr("settings.llm.quick_select"),
                    options=preset_names,
                    index=default_index,
                    help=tr("settings.llm.quick_select_help"),
                    key="llm_preset_select"
                )
                
                # Auto-fill based on selected preset
                if selected_preset != "Custom":
                    # Preset selected
                    preset_config = get_preset(selected_preset)
                    
                    # If user switched to a different preset (not current one), clear API key
                    # If it's the same as current config, keep API key
                    if selected_preset == current_preset:
                        # Same preset as saved config: keep API key
                        default_api_key = current_llm["api_key"]
                    else:
                        # Different preset: use default_api_key if provided (e.g., Ollama), otherwise clear
                        default_api_key = preset_config.get("default_api_key", "")
                    
                    default_base_url = preset_config.get("base_url", "")
                    default_model = preset_config.get("model", "")
                    
                    # Show API key URL if available
                    if preset_config.get("api_key_url"):
                        st.markdown(f"🔑 [{tr('settings.llm.get_api_key')}]({preset_config['api_key_url']})")
                else:
                    # Custom: show current saved config (if any)
                    default_api_key = current_llm["api_key"]
                    default_base_url = current_llm["base_url"]
                    default_model = current_llm["model"]
                
                st.markdown("---")
                
                # API Key (use unique key to force refresh when switching preset)
                llm_api_key = st.text_input(
                    f"{tr('settings.llm.api_key')} *",
                    value=default_api_key,
                    type="password",
                    help=tr("settings.llm.api_key_help"),
                    key=f"llm_api_key_input_{selected_preset}"
                )
                
                # Base URL (use unique key based on preset to force refresh)
                llm_base_url = st.text_input(
                    f"{tr('settings.llm.base_url')} *",
                    value=default_base_url,
                    help=tr("settings.llm.base_url_help"),
                    key=f"llm_base_url_input_{selected_preset}"
                )
                
                # Model selection with dropdown and load button
                # Initialize session state for loaded models
                if "llm_loaded_models" not in st.session_state:
                    st.session_state.llm_loaded_models = []
                
                # Build model options: Custom option + loaded models
                CUSTOM_MODEL_OPTION = f"✏️ {tr('settings.llm.custom_model')}"
                model_options = [CUSTOM_MODEL_OPTION] + st.session_state.llm_loaded_models
                
                # Determine default selection
                if default_model in st.session_state.llm_loaded_models:
                    default_model_index = model_options.index(default_model)
                else:
                    # Default model not in loaded list, use custom
                    default_model_index = 0
                
                # Model dropdown with load button on the right
                model_col, load_col, test_col = st.columns([3, 1, 1])
                
                with model_col:
                    selected_model_option = st.selectbox(
                        f"{tr('settings.llm.model')} *",
                        options=model_options,
                        index=default_model_index,
                        help=tr("settings.llm.model_help"),
                        key=f"llm_model_select_{selected_preset}"
                    )
                
                with load_col:
                    st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
                    load_clicked = st.button(
                        f"🔄 {tr('settings.llm.load_models')}",
                        help=tr("settings.llm.load_models_help"),
                        key="load_models_btn",
                        use_container_width=True
                    )
                
                with test_col:
                    st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
                    test_clicked = st.button(
                        f"🔌 {tr('settings.llm.test_connection')}",
                        help=tr("settings.llm.test_connection_help"),
                        key="test_llm_connection_btn",
                        use_container_width=True
                    )
                
                # Handle load models button click
                if load_clicked:
                    if llm_api_key and llm_base_url:
                        try:
                            from morpheus_video_studio.utils.llm_util import fetch_available_models
                            with st.spinner(tr("settings.llm.loading_models")):
                                models = fetch_available_models(llm_api_key, llm_base_url)
                                st.session_state.llm_loaded_models = models
                                st.success(tr("settings.llm.models_loaded").replace("{count}", str(len(models))))
                                safe_rerun()
                        except Exception as e:
                            st.error(tr("settings.llm.models_load_failed").replace("{error}", str(e)))
                    else:
                        st.warning(tr("status.llm_config_incomplete"))
                
                # Handle test connection button click
                if test_clicked:
                    if llm_api_key and llm_base_url:
                        try:
                            from morpheus_video_studio.utils.llm_util import test_llm_connection
                            with st.spinner(tr("settings.llm.loading_models")):
                                success, message, model_count = test_llm_connection(llm_api_key, llm_base_url)
                                if success:
                                    st.success(tr("settings.llm.connection_success").replace("{count}", str(model_count)))
                                else:
                                    st.error(tr("settings.llm.connection_failed").replace("{error}", message))
                        except Exception as e:
                            st.error(tr("settings.llm.connection_failed").replace("{error}", str(e)))
                    else:
                        st.warning(tr("status.llm_config_incomplete"))
                
                # If custom option selected, show text input for custom model name
                if selected_model_option == CUSTOM_MODEL_OPTION:
                    llm_model = st.text_input(
                        tr("settings.llm.custom_model_input"),
                        value=default_model,
                        help=tr("settings.llm.model_help"),
                        key=f"llm_custom_model_input_{selected_preset}"
                    )
                else:
                    llm_model = selected_model_option
        
        # ====================================================================
        # Column 2: ComfyUI Settings
        # ====================================================================
        with comfyui_col:
            with st.container(border=True):
                st.markdown(f"**{tr('settings.comfyui.title')}**")
                
                # Get current configuration
                comfyui_config = config_manager.get_comfyui_config()
                
                # Local/Self-hosted ComfyUI configuration
                st.markdown(f"**{tr('settings.comfyui.local_title')}**")
                url_col, key_col = st.columns(2)
                with url_col:
                    comfyui_url = st.text_input(
                        tr("settings.comfyui.comfyui_url"),
                        value=comfyui_config.get("comfyui_url", "http://127.0.0.1:8188"),
                        help=tr("settings.comfyui.comfyui_url_help"),
                        key="comfyui_url_input"
                    )
                with key_col:
                    comfyui_api_key = st.text_input(
                        tr("settings.comfyui.comfyui_api_key"),
                        value=comfyui_config.get("comfyui_api_key", ""),
                        type="password",
                        help=tr("settings.comfyui.comfyui_api_key_help"),
                        key="comfyui_api_key_input"
                    )
                
                # Test connection button
                if st.button(tr("btn.test_connection"), key="test_comfyui", use_container_width=True):
                    try:
                        import requests
                        response = requests.get(f"{comfyui_url}/system_stats", timeout=5)
                        if response.status_code == 200:
                            st.success(tr("status.connection_success"))
                        else:
                            st.error(tr("status.connection_failed"))
                    except Exception as e:
                        st.error(f"{tr('status.connection_failed')}: {str(e)}")
                
                st.caption("仅使用本地或自托管 ComfyUI 工作流，云端工作流入口已移除。")

        # ====================================================================
        # Stock Material Source Settings
        # ====================================================================
        stock_config = config_manager.get_stock_materials_config()
        provider_options = ["all", "pexels", "pixabay"]
        provider_labels = {
            "all": "全部（Pexels + Pixabay）",
            "pexels": "Pexels",
            "pixabay": "Pixabay",
        }
        current_provider = stock_config.get("default_provider", "all")
        provider_index = provider_options.index(current_provider) if current_provider in provider_options else 0

        with st.container(border=True):
            st.markdown("**素材源配置**")
            stock_provider_col, pexels_col, pixabay_col = st.columns([1, 1.4, 1.4])
            with stock_provider_col:
                stock_default_provider = st.selectbox(
                    "默认资源库",
                    provider_options,
                    format_func=lambda value: provider_labels.get(value, value),
                    index=provider_index,
                    help="素材库页面默认使用的搜索来源。",
                    key="stock_default_provider_input"
                )
            with pexels_col:
                stock_pexels_api_key = st.text_input(
                    "Pexels API Key",
                    value=stock_config.get("pexels_api_key", ""),
                    type="password",
                    help="用于 Pexels 视频素材搜索与下载。",
                    key="stock_pexels_api_key_input"
                )
            with pixabay_col:
                stock_pixabay_api_key = st.text_input(
                    "Pixabay API Key",
                    value=stock_config.get("pixabay_api_key", ""),
                    type="password",
                    help="用于 Pixabay 视频素材搜索与下载。",
                    key="stock_pixabay_api_key_input"
                )

            _, pexels_test_col, pixabay_test_col = st.columns([1, 1.4, 1.4])
            with pexels_test_col:
                if st.button("测试 Pexels", key="test_pexels_api_key", use_container_width=True):
                    if not stock_pexels_api_key.strip():
                        st.warning("请先填写 Pexels API Key。")
                    else:
                        try:
                            from morpheus_video_studio.services.moneyprinter_tools import search_stock_materials
                            with st.spinner("正在测试 Pexels..."):
                                items = run_async(
                                    search_stock_materials(
                                        "pexels",
                                        stock_pexels_api_key.strip(),
                                        "city night",
                                        "portrait",
                                        4,
                                    )
                                )
                            st.success(f"Pexels 可用，返回 {len(items)} 条素材。")
                        except Exception as e:
                            st.error(f"Pexels 测试失败：{str(e)}")

            with pixabay_test_col:
                if st.button("测试 Pixabay", key="test_pixabay_api_key", use_container_width=True):
                    if not stock_pixabay_api_key.strip():
                        st.warning("请先填写 Pixabay API Key。")
                    else:
                        try:
                            from morpheus_video_studio.services.moneyprinter_tools import search_stock_materials
                            with st.spinner("正在测试 Pixabay..."):
                                items = run_async(
                                    search_stock_materials(
                                        "pixabay",
                                        stock_pixabay_api_key.strip(),
                                        "city night",
                                        "portrait",
                                        4,
                                    )
                                )
                            st.success(f"Pixabay 可用，返回 {len(items)} 条素材。")
                        except Exception as e:
                            st.error(f"Pixabay 测试失败：{str(e)}")
        
        # ====================================================================
        # Action Buttons (full width at bottom)
        # ====================================================================
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(tr("btn.save_config"), use_container_width=True, key="save_config_btn"):
                try:
                    # Validate and save LLM configuration
                    if not (llm_api_key and llm_base_url and llm_model):
                        st.warning(tr("status.llm_config_incomplete"))
                    else:
                        config_manager.set_llm_config(llm_api_key, llm_base_url, llm_model)
                    
                    # Save ComfyUI configuration (optional fields, always save what's provided)
                    config_manager.set_comfyui_config(
                        comfyui_url=comfyui_url if comfyui_url else None,
                        comfyui_api_key=comfyui_api_key if comfyui_api_key else None,
                    )

                    # Save stock material source configuration
                    config_manager.set_stock_materials_config(
                        default_provider=stock_default_provider,
                        pexels_api_key=stock_pexels_api_key,
                        pixabay_api_key=stock_pixabay_api_key,
                    )
                    
                    config_manager.save()
                    st.success(tr("status.config_saved"))
                    safe_rerun()
                except Exception as e:
                    st.error(f"{tr('status.save_failed')}: {str(e)}")
        
        with col2:
            if st.button(tr("btn.reset_config"), use_container_width=True, key="reset_config_btn"):
                # Reset to default
                from morpheus_video_studio.config.schema import MorpheusVideoStudioConfig
                config_manager.config = MorpheusVideoStudioConfig()
                config_manager.save()
                st.success(tr("status.config_reset"))
                safe_rerun()
