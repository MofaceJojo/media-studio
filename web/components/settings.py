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


def _secret_input(label: str, *, key: str, help_text: str, has_saved_value: bool) -> str:
    value = st.text_input(
        label,
        value="",
        type="password",
        help=help_text,
        placeholder="留空则保留本地已保存值" if has_saved_value else "",
        key=key,
    )
    if has_saved_value:
        st.caption("已保存本地密钥。留空则继续使用，不会在页面直接回显。")
    return value


def _get_hyperframe_config() -> dict:
    """Read HyperFrame config with compatibility for already-running Streamlit sessions."""
    if hasattr(config_manager, "get_hyperframe_config"):
        return config_manager.get_hyperframe_config()

    config_dict = config_manager.config.to_dict() if hasattr(config_manager.config, "to_dict") else {}
    return {
        "enabled": True,
        "command": "npx --yes hyperframes",
        "quality": "draft",
        "fps": 30,
        "timeout_seconds": 300,
        **config_dict.get("hyperframe", {}),
    }


def _set_hyperframe_config(**updates):
    """Write HyperFrame config with compatibility for already-running Streamlit sessions."""
    if hasattr(config_manager, "set_hyperframe_config"):
        config_manager.set_hyperframe_config(**updates)
    else:
        config_manager.update({"hyperframe": updates})


def _get_notebooklm_config() -> dict:
    """Read NotebookLM config with compatibility for already-running Streamlit sessions."""
    if hasattr(config_manager, "get_notebooklm_config"):
        return config_manager.get_notebooklm_config()

    config_dict = config_manager.config.to_dict() if hasattr(config_manager.config, "to_dict") else {}
    return {
        "enabled": False,
        "profile": "default",
        "auth_json_path": "",
        "language": "Chinese",
        "report_format": "study_guide",
        "timeout_seconds": 300,
        "auto_cleanup_notebook": True,
        **config_dict.get("notebooklm", {}),
    }


def _get_local_services_config() -> dict:
    """Read local service launcher config with compatibility for already-running Streamlit sessions."""
    if hasattr(config_manager, "get_local_services_config"):
        return config_manager.get_local_services_config()

    config_dict = config_manager.config.to_dict() if hasattr(config_manager.config, "to_dict") else {}
    return {
        "comfyui": {"workdir": "", "command": ""},
        "omnivoice": {"workdir": "", "command": ""},
        "web": {"workdir": "", "command": ""},
        **config_dict.get("local_services", {}),
    }


def render_advanced_settings():
    """Render system configuration (required) with 2-column layout"""
    # Always reflect what's on disk: config.yaml may have been changed by
    # another page, a script, or a previous session. Without this, the form
    # shows boot-time values and save() writes that stale snapshot back —
    # which looks to the user like "my settings won't save".
    try:
        config_manager.reload()
    except Exception as exc:  # keep the page usable even if reload fails
        st.warning(f"配置文件重新读取失败，页面可能显示旧值：{exc}")

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
                from morpheus_video_studio.llm_presets import (
                    get_preset_names,
                    get_preset,
                    find_preset_by_base_url_and_model,
                    find_preset_by_base_url,
                )

                # Custom at the end
                preset_names = get_preset_names() + ["Custom"]

                # Get current config
                current_llm = config_manager.get_llm_config()

                # Auto-detect which preset matches current config.
                # A custom model on a known provider (e.g. an OpenRouter
                # :free model) still counts as that provider, otherwise
                # returning to this page drops to "Custom" and the saved
                # credentials look lost.
                current_preset = find_preset_by_base_url_and_model(
                    current_llm["base_url"],
                    current_llm["model"]
                ) or find_preset_by_base_url(current_llm["base_url"])

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
                    default_api_key = preset_config.get("default_api_key", "") if selected_preset != current_preset else ""
                    default_base_url = preset_config.get("base_url", "")
                    # Keep the saved (possibly custom) model when this preset
                    # is the provider of the saved config
                    if selected_preset == current_preset and current_llm["model"]:
                        default_model = current_llm["model"]
                    else:
                        default_model = preset_config.get("model", "")

                    # Show API key URL if available
                    if preset_config.get("api_key_url"):
                        st.markdown(f"🔑 [{tr('settings.llm.get_api_key')}]({preset_config['api_key_url']})")
                else:
                    # Custom: show current saved config (if any)
                    default_api_key = ""
                    default_base_url = current_llm["base_url"]
                    default_model = current_llm["model"]
                
                st.markdown("---")
                
                # API Key (use unique key to force refresh when switching preset)
                # The saved key stays usable when we're still on the same
                # provider: preset matches, or both saved & selected are Custom.
                saved_key_applies = (
                    selected_preset == current_preset
                    or (selected_preset == "Custom" and current_preset is None)
                )
                llm_api_key = _secret_input(
                    f"{tr('settings.llm.api_key')} *",
                    help_text=tr("settings.llm.api_key_help"),
                    has_saved_value=bool(current_llm["api_key"].strip()) and saved_key_applies,
                    key=f"llm_api_key_input_{selected_preset}"
                )
                effective_llm_api_key = (
                    llm_api_key.strip()
                    or (current_llm["api_key"].strip() if saved_key_applies else "")
                    or default_api_key
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
                    if effective_llm_api_key and llm_base_url:
                        try:
                            from morpheus_video_studio.utils.llm_util import fetch_available_models
                            with st.spinner(tr("settings.llm.loading_models")):
                                models = fetch_available_models(effective_llm_api_key, llm_base_url)
                                st.session_state.llm_loaded_models = models
                                st.success(tr("settings.llm.models_loaded").replace("{count}", str(len(models))))
                                safe_rerun()
                        except Exception as e:
                            st.error(tr("settings.llm.models_load_failed").replace("{error}", str(e)))
                    else:
                        st.warning(tr("status.llm_config_incomplete"))
                
                # Handle test connection button click
                if test_clicked:
                    if effective_llm_api_key and llm_base_url:
                        try:
                            from morpheus_video_studio.utils.llm_util import test_llm_connection
                            with st.spinner(tr("settings.llm.loading_models")):
                                success, message, model_count = test_llm_connection(effective_llm_api_key, llm_base_url)
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
                st.caption("模型名可以填任意 OpenAI-compatible model id；如果你有自定义模型，例如 noun research，直接填真实 model id 即可。")
        
        # ====================================================================
        # Column 2: ComfyUI Settings
        # ====================================================================
        with comfyui_col:
            with st.container(border=True):
                st.markdown(f"**{tr('settings.comfyui.title')}**")
                
                # Get current configuration
                comfyui_config = config_manager.get_comfyui_config()
                hyperframe_config = _get_hyperframe_config()
                notebooklm_config = _get_notebooklm_config()
                
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
                    comfyui_api_key = _secret_input(
                        tr("settings.comfyui.comfyui_api_key"),
                        help_text=tr("settings.comfyui.comfyui_api_key_help"),
                        has_saved_value=bool((comfyui_config.get("comfyui_api_key") or "").strip()),
                        key="comfyui_api_key_input"
                    )
                effective_comfyui_api_key = comfyui_api_key.strip() or (comfyui_config.get("comfyui_api_key") or "").strip()
                
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

                st.markdown("---")
                st.markdown("**HyperFrame 本地渲染**")
                hyperframe_enabled = st.checkbox(
                    "启用 HyperFrame 视频片段生成",
                    value=hyperframe_config.get("enabled", True),
                    help="视频模板需要生成视频素材时，可以使用 HyperFrame 作为 ComfyUI 视频工作流的替代选项。",
                    key="hyperframe_enabled_input"
                )
                hyperframe_command = st.text_input(
                    "HyperFrame 命令",
                    value=hyperframe_config.get("command", "npx --yes hyperframes"),
                    help="默认使用 npx --yes hyperframes；如果你全局安装了 hyperframes，也可以填 hyperframes。",
                    key="hyperframe_command_input"
                )
                quality_col, fps_col, timeout_col = st.columns(3)
                with quality_col:
                    quality_options = ["draft", "standard", "high"]
                    saved_quality = hyperframe_config.get("quality", "draft")
                    hyperframe_quality = st.selectbox(
                        "质量",
                        quality_options,
                        index=quality_options.index(saved_quality) if saved_quality in quality_options else 0,
                        key="hyperframe_quality_input"
                    )
                with fps_col:
                    hyperframe_fps = st.number_input(
                        "FPS",
                        min_value=15,
                        max_value=60,
                        value=int(hyperframe_config.get("fps", 30)),
                        step=5,
                        key="hyperframe_fps_input"
                    )
                with timeout_col:
                    hyperframe_timeout = st.number_input(
                        "超时(秒)",
                        min_value=30,
                        max_value=1800,
                        value=int(hyperframe_config.get("timeout_seconds", 300)),
                        step=30,
                        key="hyperframe_timeout_input"
                    )

                if st.button("测试 HyperFrame", key="test_hyperframe", use_container_width=True):
                    try:
                        from morpheus_video_studio.utils.hyperframe_util import check_hyperframe_health

                        ok, msg = check_hyperframe_health(hyperframe_command, timeout=10.0)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                    except Exception as e:
                        st.error(f"HyperFrame 测试失败：{str(e)}")

                st.markdown("---")
                st.markdown("**NotebookLM Beta**")
                notebooklm_enabled = st.checkbox(
                    "启用 NotebookLM 文档解读增强",
                    value=bool(notebooklm_config.get("enabled", False)),
                    help="仅用于文档转视频的内容理解增强；默认流程仍然使用本地 LLM 解读。",
                    key="notebooklm_enabled_input",
                )
                notebooklm_profile = st.text_input(
                    "NotebookLM profile",
                    value=notebooklm_config.get("profile", "default"),
                    help="如果你已经用 notebooklm-py 登录过，本地 profile 通常是 default。",
                    key="notebooklm_profile_input",
                )
                notebooklm_auth_path = st.text_input(
                    "认证文件路径（可选）",
                    value=notebooklm_config.get("auth_json_path", ""),
                    help="填写 notebooklm-py 的 storage_state.json；留空则尝试 profile 或 NOTEBOOKLM_AUTH_JSON。",
                    key="notebooklm_auth_path_input",
                )
                notebooklm_language_col, notebooklm_format_col = st.columns(2)
                with notebooklm_language_col:
                    notebooklm_language = st.text_input(
                        "输出语言",
                        value=notebooklm_config.get("language", "Chinese"),
                        help="例如 Chinese、English。",
                        key="notebooklm_language_input",
                    )
                with notebooklm_format_col:
                    report_options = ["study_guide", "briefing_doc", "blog_post", "custom"]
                    saved_report_format = notebooklm_config.get("report_format", "study_guide")
                    notebooklm_report_format = st.selectbox(
                        "报告格式",
                        report_options,
                        index=report_options.index(saved_report_format) if saved_report_format in report_options else 0,
                        key="notebooklm_report_format_input",
                    )
                notebooklm_timeout = st.number_input(
                    "超时(秒)",
                    min_value=60,
                    max_value=1800,
                    value=int(notebooklm_config.get("timeout_seconds", 300)),
                    step=30,
                    key="notebooklm_timeout_input",
                )
                notebooklm_auto_cleanup = st.checkbox(
                    "生成后自动清理临时 Notebook",
                    value=bool(notebooklm_config.get("auto_cleanup_notebook", True)),
                    key="notebooklm_auto_cleanup_input",
                )
                if st.button("测试 NotebookLM", key="test_notebooklm", use_container_width=True):
                    try:
                        from morpheus_video_studio.services.notebooklm_service import NotebookLMService

                        service = NotebookLMService(
                            {
                                "enabled": notebooklm_enabled,
                                "profile": notebooklm_profile,
                                "auth_json_path": notebooklm_auth_path,
                                "language": notebooklm_language,
                                "report_format": notebooklm_report_format,
                                "timeout_seconds": int(notebooklm_timeout),
                                "auto_cleanup_notebook": notebooklm_auto_cleanup,
                            }
                        )
                        ok, message = run_async(service.test_connection())
                        if ok:
                            st.success(message)
                        else:
                            st.error(message)
                    except Exception as e:
                        st.error(f"NotebookLM 测试失败：{str(e)}")

        # ====================================================================
        # Stock Material Source Settings
        # ====================================================================
        stock_config = config_manager.get_stock_materials_config()
        service_launcher_config = _get_local_services_config()
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
                    value="",
                    type="password",
                    help="用于 Pexels 视频素材搜索与下载。",
                    placeholder="留空则保留本地已保存值" if stock_config.get("pexels_api_key", "").strip() else "",
                    key="stock_pexels_api_key_input"
                )
                if stock_config.get("pexels_api_key", "").strip():
                    st.caption("已保存本地 Pexels 密钥。留空则继续使用，不会在页面回显。")
            with pixabay_col:
                stock_pixabay_api_key = st.text_input(
                    "Pixabay API Key",
                    value="",
                    type="password",
                    help="用于 Pixabay 视频素材搜索与下载。",
                    placeholder="留空则保留本地已保存值" if stock_config.get("pixabay_api_key", "").strip() else "",
                    key="stock_pixabay_api_key_input"
                )
                if stock_config.get("pixabay_api_key", "").strip():
                    st.caption("已保存本地 Pixabay 密钥。留空则继续使用，不会在页面回显。")
            effective_pexels_api_key = stock_pexels_api_key.strip() or stock_config.get("pexels_api_key", "").strip()
            effective_pixabay_api_key = stock_pixabay_api_key.strip() or stock_config.get("pixabay_api_key", "").strip()

            _, pexels_test_col, pixabay_test_col = st.columns([1, 1.4, 1.4])
            with pexels_test_col:
                if st.button("测试 Pexels", key="test_pexels_api_key", use_container_width=True):
                    if not effective_pexels_api_key:
                        st.warning("请先填写 Pexels API Key。")
                    else:
                        try:
                            from morpheus_video_studio.services.stock_publish_tools import search_stock_materials
                            with st.spinner("正在测试 Pexels..."):
                                items = run_async(
                                    search_stock_materials(
                                        "pexels",
                                        effective_pexels_api_key,
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
                    if not effective_pixabay_api_key:
                        st.warning("请先填写 Pixabay API Key。")
                    else:
                        try:
                            from morpheus_video_studio.services.stock_publish_tools import search_stock_materials
                            with st.spinner("正在测试 Pixabay..."):
                                items = run_async(
                                    search_stock_materials(
                                        "pixabay",
                                        effective_pixabay_api_key,
                                        "city night",
                                        "portrait",
                                        4,
                                    )
                                )
                            st.success(f"Pixabay 可用，返回 {len(items)} 条素材。")
                        except Exception as e:
                            st.error(f"Pixabay 测试失败：{str(e)}")

        with st.container(border=True):
            st.markdown("**本地服务控制**")
            st.caption("把常用的本地服务启动命令记在这里，后面可以直接一键启动 ComfyUI、OmniVoice 和 Media Studio Web。")

            from morpheus_video_studio.utils.service_launcher import (
                detect_default_service_command,
                detect_default_service_workdir,
                check_web_health,
                start_local_service,
            )
            from morpheus_video_studio.utils.comfyui_util import check_comfyui_health
            from morpheus_video_studio.utils.omnivoice_util import check_omnivoice_health

            saved_comfy_service = service_launcher_config.get("comfyui", {})
            saved_omni_service = service_launcher_config.get("omnivoice", {})
            saved_web_service = service_launcher_config.get("web", {})

            comfy_workdir_default = saved_comfy_service.get("workdir") or detect_default_service_workdir("comfyui")
            comfy_command_default = saved_comfy_service.get("command") or detect_default_service_command(
                "comfyui",
                comfy_workdir_default,
            )
            omni_workdir_default = saved_omni_service.get("workdir") or detect_default_service_workdir("omnivoice")
            omni_command_default = saved_omni_service.get("command") or detect_default_service_command(
                "omnivoice",
                omni_workdir_default,
            )
            web_workdir_default = saved_web_service.get("workdir") or detect_default_service_workdir("web")
            web_command_default = saved_web_service.get("command") or detect_default_service_command(
                "web",
                web_workdir_default,
            )

            services_col1, services_col2 = st.columns(2, gap="large")
            with services_col1:
                st.markdown("**ComfyUI**")
                comfy_ok, comfy_status = check_comfyui_health(comfyui_url, timeout=3.0)
                if comfy_ok:
                    st.success(comfy_status)
                else:
                    st.warning(comfy_status)
                comfyui_service_workdir = st.text_input(
                    "ComfyUI 目录",
                    value=comfy_workdir_default,
                    key="service_comfyui_workdir_input",
                )
                comfyui_service_command = st.text_input(
                    "ComfyUI 启动命令",
                    value=comfy_command_default,
                    key="service_comfyui_command_input",
                    help="默认会直接运行本地 ComfyUI main.py。",
                )
                comfy_start_col, comfy_refresh_col = st.columns(2)
                with comfy_start_col:
                    if st.button("启动 ComfyUI", key="service_start_comfyui", use_container_width=True):
                        try:
                            result = start_local_service(
                                "comfyui",
                                workdir=comfyui_service_workdir,
                                command=comfyui_service_command,
                                base_url=comfyui_url,
                            )
                            if result["ok"]:
                                st.success(result["message"])
                            else:
                                st.info(result["message"])
                        except Exception as e:
                            st.error(f"ComfyUI 启动失败：{str(e)}")
                with comfy_refresh_col:
                    if st.button("刷新状态", key="service_refresh_comfyui", use_container_width=True):
                        st.rerun()

            with services_col2:
                st.markdown("**OmniVoice**")
                omni_base_url = comfyui_config.get("tts", {}).get("omnivoice", {}).get("base_url", "http://127.0.0.1:3900")
                omni_ok, omni_status = check_omnivoice_health(omni_base_url, timeout=3.0)
                if omni_ok:
                    st.success(omni_status)
                else:
                    st.warning(omni_status)
                omnivoice_service_workdir = st.text_input(
                    "OmniVoice 目录",
                    value=omni_workdir_default,
                    key="service_omnivoice_workdir_input",
                )
                omnivoice_service_command = st.text_input(
                    "OmniVoice 启动命令",
                    value=omni_command_default,
                    key="service_omnivoice_command_input",
                    help="默认使用 bun run dev，同时拉起 3900 后端和前端。",
                )
                omni_start_col, omni_refresh_col = st.columns(2)
                with omni_start_col:
                    if st.button("启动 OmniVoice", key="service_start_omnivoice", use_container_width=True):
                        try:
                            result = start_local_service(
                                "omnivoice",
                                workdir=omnivoice_service_workdir,
                                command=omnivoice_service_command,
                                base_url=omni_base_url,
                                wait_seconds=12.0,
                            )
                            if result["ok"]:
                                st.success(result["message"])
                            else:
                                st.info(result["message"])
                        except Exception as e:
                            st.error(f"OmniVoice 启动失败：{str(e)}")
                with omni_refresh_col:
                    if st.button("刷新状态", key="service_refresh_omnivoice", use_container_width=True):
                        st.rerun()

            with st.container(border=True):
                st.markdown("**Media Studio Web**")
                web_base_url = "http://127.0.0.1:8501"
                web_ok, web_status = check_web_health(web_base_url, timeout=3.0)
                if web_ok:
                    st.success(web_status)
                else:
                    st.warning(web_status)
                web_service_workdir = st.text_input(
                    "Web 目录",
                    value=web_workdir_default,
                    key="service_web_workdir_input",
                )
                web_service_command = st.text_input(
                    "Web 启动命令",
                    value=web_command_default,
                    key="service_web_command_input",
                    help="默认启动当前项目的 Streamlit Web 界面。",
                )
                web_start_col, web_refresh_col = st.columns(2)
                with web_start_col:
                    if st.button("启动 Web", key="service_start_web", use_container_width=True):
                        try:
                            result = start_local_service(
                                "web",
                                workdir=web_service_workdir,
                                command=web_service_command,
                                base_url=web_base_url,
                                wait_seconds=10.0,
                            )
                            if result["ok"]:
                                st.success(result["message"])
                            else:
                                st.info(result["message"])
                        except Exception as e:
                            st.error(f"Web 启动失败：{str(e)}")
                with web_refresh_col:
                    if st.button("刷新状态", key="service_refresh_web", use_container_width=True):
                        st.rerun()

        # ====================================================================
        # Action Buttons (full width at bottom)
        # ====================================================================
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(tr("btn.save_config"), use_container_width=True, key="save_config_btn"):
                try:
                    # Validate and save LLM configuration
                    llm_saved = bool(effective_llm_api_key and llm_base_url and llm_model)
                    if llm_saved:
                        config_manager.set_llm_config(effective_llm_api_key, llm_base_url, llm_model)
                    
                    # Save ComfyUI configuration (optional fields, always save what's provided)
                    config_manager.set_comfyui_config(
                        comfyui_url=comfyui_url if comfyui_url else None,
                        comfyui_api_key=effective_comfyui_api_key if effective_comfyui_api_key else None,
                    )

                    _set_hyperframe_config(
                        enabled=hyperframe_enabled,
                        command=hyperframe_command,
                        quality=hyperframe_quality,
                        fps=int(hyperframe_fps),
                        timeout_seconds=int(hyperframe_timeout),
                    )

                    config_manager.set_notebooklm_config(
                        enabled=notebooklm_enabled,
                        profile=notebooklm_profile,
                        auth_json_path=notebooklm_auth_path,
                        language=notebooklm_language,
                        report_format=notebooklm_report_format,
                        timeout_seconds=int(notebooklm_timeout),
                        auto_cleanup_notebook=notebooklm_auto_cleanup,
                    )

                    config_manager.set_local_services_config(
                        comfyui_workdir=comfyui_service_workdir,
                        comfyui_command=comfyui_service_command,
                        omnivoice_workdir=omnivoice_service_workdir,
                        omnivoice_command=omnivoice_service_command,
                        web_workdir=web_service_workdir,
                        web_command=web_service_command,
                    )

                    # Save stock material source configuration
                    config_manager.set_stock_materials_config(
                        default_provider=stock_default_provider,
                        pexels_api_key=effective_pexels_api_key,
                        pixabay_api_key=effective_pixabay_api_key,
                    )
                    
                    config_manager.save()
                    if llm_saved:
                        st.success(tr("status.config_saved"))
                    else:
                        missing = [
                            label for label, value in (
                                ("API Key", effective_llm_api_key),
                                ("Base URL", llm_base_url),
                                ("模型名", llm_model),
                            ) if not value
                        ]
                        st.error(
                            f"⚠️ LLM 配置未保存：缺少 {'、'.join(missing)}。"
                            "其余设置已保存。请补齐后再点一次保存。"
                        )
                    if llm_saved:
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
