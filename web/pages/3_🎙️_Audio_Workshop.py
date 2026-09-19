import json
import sys
import uuid
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from loguru import logger

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from morpheus_video_studio.config import config_manager
from morpheus_video_studio.services.studio_library import StudioLibraryService
from morpheus_video_studio.utils.omnivoice_util import (
    build_omnivoice_profile_audio_url,
    check_omnivoice_health,
    create_omnivoice_transcription,
    delete_omnivoice_profile,
    fetch_omnivoice_catalog,
    fetch_omnivoice_model_status,
    fetch_omnivoice_profiles,
    format_omnivoice_error,
    generate_omnivoice_audio,
    normalize_omnivoice_instruct,
)
from web.components.faq import render_faq_sidebar
from web.components.studio_shell import inject_studio_css, render_studio_hero, render_workspace_context
from web.components.tts_preferences import (
    get_local_tts_preferences,
    get_omnivoice_tts_preferences,
    persist_local_tts_preferences,
    persist_omnivoice_tts_preferences,
)
from web.state.session import get_morpheus_video_studio, init_i18n, init_session_state
from web.utils.async_helpers import run_async


OMNIVOICE_POPULAR_LANGUAGES = [
    "Auto",
    "English",
    "Chinese",
    "Japanese",
    "Korean",
    "Spanish",
    "French",
    "German",
    "Italian",
    "Portuguese",
    "Russian",
    "Arabic",
    "Hindi",
]

OMNIVOICE_EXPRESSION_TAGS = [
    "[laughter]",
    "[sigh]",
    "[confirmation-en]",
    "[question-en]",
    "[question-ah]",
    "[question-oh]",
    "[question-ei]",
    "[question-yi]",
    "[surprise-ah]",
    "[surprise-oh]",
    "[surprise-wa]",
    "[surprise-yo]",
    "[dissatisfaction-hnn]",
]

OMNIVOICE_TIMEOUT_READY_SECONDS = 600.0
OMNIVOICE_TIMEOUT_COLD_START_SECONDS = 1200.0


@st.cache_data(ttl=5, show_spinner=False)
def _fetch_omnivoice_workspace() -> dict:
    comfyui_config = config_manager.get_comfyui_config()
    tts_config = comfyui_config["tts"]
    omni_config = tts_config.get("omnivoice", {})
    base_url = omni_config.get("base_url", "http://127.0.0.1:3900").rstrip("/")
    frontend_url = omni_config.get("frontend_url", "http://localhost:3901/").rstrip("/") + "/"

    ok, status = check_omnivoice_health(base_url)
    catalog = {"voices": [], "engines": []}
    profiles: list[dict] = []
    model_status: dict | None = None
    if ok:
        try:
            catalog = fetch_omnivoice_catalog(base_url, timeout=4.0)
        except Exception as exc:
            logger.warning(f"Failed to fetch OmniVoice catalog: {exc}")
        try:
            profiles = fetch_omnivoice_profiles(base_url, timeout=4.0)
        except Exception as exc:
            logger.warning(f"Failed to fetch OmniVoice profiles: {exc}")
        try:
            model_status = fetch_omnivoice_model_status(base_url, timeout=4.0)
        except Exception as exc:
            logger.warning(f"Failed to fetch OmniVoice model status: {exc}")

    return {
        "base_url": base_url,
        "frontend_url": frontend_url,
        "ok": ok,
        "status": status,
        "catalog": catalog,
        "profiles": profiles,
        "model_status": model_status,
        "config": omni_config,
    }


def _get_omnivoice_workspace() -> dict:
    return _fetch_omnivoice_workspace()


def _engine_available(workspace: dict, engine_id: str) -> bool:
    return any(
        item.get("id") == engine_id and item.get("available")
        for item in workspace["catalog"].get("engines", [])
    )


def _show_omnivoice_notice() -> None:
    notice = st.session_state.pop("studio_audio_omni_notice", None)
    if notice:
        st.success(notice)


def _append_clone_prompt_tag(tag: str) -> None:
    current = st.session_state.get("studio_clone_prompt_text", "")
    if current and not current.endswith((" ", "\n")):
        current += " "
    st.session_state["studio_clone_prompt_text"] = f"{current}{tag} "


def _persist_generated_audio(audio_bytes: bytes, suffix: str = ".wav") -> str:
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"omnivoice_clone_{uuid.uuid4().hex[:12]}{suffix}"
    output_path.write_bytes(audio_bytes)
    return str(output_path.resolve())


def _render_omnivoice_connection(workspace: dict) -> None:
    if workspace["ok"]:
        st.success(workspace["status"])
    else:
        st.warning(workspace["status"])
    model_status = workspace.get("model_status") or {}
    if workspace["ok"] and model_status:
        status = model_status.get("status")
        loaded = bool(model_status.get("loaded"))
        loading = bool(model_status.get("loading"))
        detail = (model_status.get("detail") or model_status.get("sub_stage") or "").strip()
        progress = model_status.get("progress")
        progress_text = f" · {progress}%" if progress is not None else ""

        if loading and detail == "Model ready" and not loaded:
            st.warning("OmniVoice 模型状态异常：显示已就绪，但后端仍停留在 loading。建议重启 OmniVoice Studio。")
        elif status == "ready" or loaded:
            st.caption("模型状态：已就绪")
        elif status == "loading" or loading:
            suffix = f" · {detail}" if detail else ""
            st.caption(f"模型状态：加载中{progress_text}{suffix}")
        elif status == "idle":
            st.caption("模型状态：空闲，首次生成会先预热模型。")
    action_col, info_col = st.columns([1, 2], gap="small")
    with action_col:
        st.markdown(f"[打开 OmniVoice Studio]({workspace['frontend_url']})")
    with info_col:
        st.caption(f"后端：`{workspace['base_url']}`  ·  前端：`{workspace['frontend_url']}`")


def _build_tts_config(workspace: dict) -> dict:
    comfyui_config = config_manager.get_comfyui_config()
    tts_config = comfyui_config["tts"]
    omni_config = workspace["config"]

    mode = st.radio(
        "语音引擎",
        ["omnivoice", "local", "comfyui"],
        horizontal=True,
        format_func=lambda value: {
            "omnivoice": "OmniVoice 本地",
            "local": "Edge TTS 本地",
            "comfyui": "ComfyUI TTS",
        }[value],
        index={"omnivoice": 0, "local": 1, "comfyui": 2}.get(tts_config.get("inference_mode", "local"), 1),
        key="studio_audio_tts_mode",
    )

    voice = None
    speed = None
    instruct = None
    workflow = None
    ref_audio = None
    model = None
    base_url = None

    if mode == "omnivoice":
        base_url = workspace["base_url"]
        _render_omnivoice_connection(workspace)

        voice_items = workspace["catalog"].get("voices", []) if workspace["ok"] else []
        engine_items = workspace["catalog"].get("engines", []) if workspace["ok"] else []

        available_engines = [item for item in engine_items if item.get("available")]
        saved_voice, saved_speed, saved_model, saved_instruct = get_omnivoice_tts_preferences(
            omni_config.get("voice", "default"),
            float(omni_config.get("speed", 1.0)),
            omni_config.get("model", "omnivoice"),
            normalize_omnivoice_instruct(omni_config.get("instruct")) or "男，青年",
        )
        engine_ids = [item.get("id") for item in available_engines if item.get("id")]
        engine_labels = [
            f"{item.get('display_name') or item.get('id')} ({item.get('id')})"
            for item in available_engines
            if item.get("id")
        ]
        if not engine_ids:
            engine_ids = [saved_model]
            engine_labels = [saved_model]
        elif saved_model not in engine_ids:
            engine_ids.append(saved_model)
            engine_labels.append(f"{saved_model} (当前配置)")
        default_model_index = engine_ids.index(saved_model) if saved_model in engine_ids else 0

        preferred_voice = st.session_state.get("studio_audio_preferred_omni_voice")
        voice_ids = [item.get("voice_id") for item in voice_items if item.get("voice_id")]
        voice_labels = []
        voice_lookup: dict[str, dict] = {}
        for item in voice_items:
            voice_id = item.get("voice_id")
            if not voice_id:
                continue
            voice_lookup[voice_id] = item
            meta = " · ".join(part for part in [item.get("type"), item.get("language")] if part)
            label = item.get("name") or voice_id
            voice_labels.append(f"{label} ({voice_id})" + (f" · {meta}" if meta else ""))

        saved_voice_in_catalog = saved_voice in voice_ids
        if not voice_ids:
            voice_ids = ["default", "alloy", "nova", "demo0001"]
            voice_labels = ["Default", "Alloy", "Nova", "OmniVoice Demo"]
        elif not saved_voice_in_catalog:
            voice_ids.append(saved_voice)
            voice_labels.append(f"{saved_voice} (当前配置)")

        default_voice_index = 0
        if saved_voice_in_catalog:
            default_voice_index = voice_ids.index(saved_voice)
        else:
            profile_candidates = [
                idx for idx, item in enumerate(voice_ids)
                if voice_lookup.get(item, {}).get("type") == "profile"
            ]
            if profile_candidates:
                default_voice_index = profile_candidates[0]

        voice_col, engine_col = st.columns([1.15, 0.85], gap="small")
        with voice_col:
            selected_voice_display = st.selectbox(
                "音色",
                voice_labels,
                index=default_voice_index,
                key="studio_audio_omni_voice_v2",
            )
            voice = voice_ids[voice_labels.index(selected_voice_display)]
        with engine_col:
            selected_engine_display = st.selectbox(
                "模型/引擎",
                engine_labels,
                index=default_model_index,
                key="studio_audio_omni_model_v2",
            )
            model = engine_ids[engine_labels.index(selected_engine_display)]

        selected_voice_meta = voice_lookup.get(voice)
        if preferred_voice and preferred_voice == voice:
            st.caption(f"已从音色库带入当前音色：`{voice}`")
        if selected_voice_meta:
            meta_bits = [
                selected_voice_meta.get("type"),
                selected_voice_meta.get("language"),
                selected_voice_meta.get("description"),
            ]
            st.caption(" · ".join(bit for bit in meta_bits if bit))

        speed = st.slider("语速", 0.25, 4.0, float(saved_speed), 0.1, key="studio_audio_omni_speed")
        instruct = st.text_input(
            "风格指令",
            value=saved_instruct,
            help="建议用简短预设标签，例如：男，青年 / 女，青年。不要写长段英文描述。",
            key="studio_audio_omni_instruct_v2",
        )
        persist_omnivoice_tts_preferences(
            voice,
            speed,
            model=model,
            instruct=instruct,
        )
    elif mode == "local":
        local_config = tts_config.get("local", {})
        from morpheus_video_studio.tts_voices import EDGE_TTS_VOICES, get_voice_display_name
        from web.i18n import get_language, tr

        voice_options = [get_voice_display_name(item["id"], tr, get_language()) for item in EDGE_TTS_VOICES]
        voice_ids = [item["id"] for item in EDGE_TTS_VOICES]
        saved_voice, saved_speed = get_local_tts_preferences(
            local_config.get("voice", "zh-CN-YunjianNeural"),
            float(local_config.get("speed", 1.2)),
        )
        default_idx = voice_ids.index(saved_voice) if saved_voice in voice_ids else 0
        selected_label = st.selectbox("音色", voice_options, index=default_idx, key="studio_audio_local_voice")
        voice = voice_ids[voice_options.index(selected_label)]
        speed = st.slider("语速", 0.5, 2.0, float(saved_speed), 0.1, key="studio_audio_local_speed")
        persist_local_tts_preferences(voice, speed)
    else:
        workflow = "selfhost/tts_edge.json"
        ref_audio_file = st.file_uploader(
            "参考音频（可选）",
            type=["mp3", "wav", "m4a", "aac", "ogg", "flac"],
            key="studio_audio_ref_audio",
        )
        if ref_audio_file is not None:
            ref_dir = Path("temp/audio_workshop")
            ref_dir.mkdir(parents=True, exist_ok=True)
            ref_audio_path = ref_dir / ref_audio_file.name
            ref_audio_path.write_bytes(ref_audio_file.getbuffer())
            ref_audio = str(ref_audio_path.resolve())
            st.audio(ref_audio)

    return {
        "tts_inference_mode": mode,
        "tts_voice": voice,
        "tts_speed": speed,
        "tts_instruct": normalize_omnivoice_instruct(instruct) if mode == "omnivoice" else None,
        "tts_model": model if mode == "omnivoice" else None,
        "tts_base_url": base_url if mode == "omnivoice" else None,
        "tts_workflow": workflow,
        "ref_audio": ref_audio,
    }


def _render_dubbing_tab(library: StudioLibraryService, workspace: dict) -> None:
    content_items = library.list_content_items()
    audio_assets = library.list_audio_assets()
    selected_content_id = st.session_state.get("studio_selected_content_id")
    selected_item = library.get_content_item(selected_content_id) if selected_content_id else None

    if not content_items and st.session_state.get("studio_audio_source_mode") == "content_library":
        st.session_state["studio_audio_source_mode"] = "direct_text"
    elif content_items and selected_content_id and "studio_audio_source_mode" not in st.session_state:
        st.session_state["studio_audio_source_mode"] = "content_library"
    elif "studio_audio_source_mode" not in st.session_state:
        st.session_state["studio_audio_source_mode"] = "direct_text"

    source_col, config_col = st.columns([1.05, 0.95], gap="large")
    with source_col:
        with st.container(border=True):
            st.markdown("### 文本来源")
            source_mode = st.radio(
                "来源",
                ["content_library", "direct_text"],
                horizontal=True,
                format_func=lambda value: {
                    "content_library": "从内容库选择",
                    "direct_text": "直接输入",
                }[value],
                key="studio_audio_source_mode",
            )

            content_id = None
            selected_text = ""
            title = ""
            if source_mode == "content_library":
                if not content_items:
                    st.info("内容库还没有条目。先去导入 PDF、Word 或文本内容。")
                else:
                    content_ids = [item["content_id"] for item in content_items]
                    preferred_id = st.session_state.get("studio_selected_content_id")
                    default_idx = content_ids.index(preferred_id) if preferred_id in content_ids else 0
                    selected_label = st.selectbox(
                        "内容条目",
                        options=list(range(len(content_items))),
                        format_func=lambda idx: f"{content_items[idx]['title']} · {content_items[idx].get('content_type', 'content')}",
                        index=default_idx,
                        key="studio_audio_content_item",
                    )
                    selected_item = content_items[selected_label]
                    content_id = selected_item["content_id"]
                    title = selected_item["title"]
                    extracted_path = selected_item.get("extracted_text_path")
                    if extracted_path and Path(extracted_path).exists():
                        selected_text = Path(extracted_path).read_text(encoding="utf-8")
                    st.info(f"当前已从内容库带入：{title}")
                    with st.expander("查看内容预览", expanded=False):
                        st.text_area("内容文本", value=selected_text, height=260)
            else:
                title = st.text_input("音频标题", key="studio_audio_direct_title")
                selected_text = st.text_area(
                    "朗读文本",
                    height=260,
                    placeholder="输入一段要合成旁白的文本，或从内容库先沉淀一条内容再回来做音频。",
                    key="studio_audio_direct_text",
                )

            asset_title = st.text_input("保存标题", value=title, key="studio_audio_asset_title")
            tags = st.text_input("标签（逗号分隔）", key="studio_audio_tags")

    with config_col:
        with st.container(border=True):
            st.markdown("### 语音配置")
            tts_config = _build_tts_config(workspace)

        with st.container(border=True):
            st.markdown("### 生成与入库")
            if st.button("生成声音素材", type="primary", width="stretch", key="studio_generate_audio"):
                if not selected_text.strip():
                    st.error("请先提供要合成的文本。")
                else:
                    try:
                        params = {
                            "text": selected_text,
                            "inference_mode": tts_config["tts_inference_mode"],
                            "voice": tts_config["tts_voice"],
                            "speed": tts_config["tts_speed"],
                            "workflow": tts_config["tts_workflow"],
                            "output_path": None,
                        }
                        if tts_config["tts_inference_mode"] == "omnivoice":
                            params["instruct"] = tts_config["tts_instruct"]
                            params["model"] = tts_config["tts_model"]
                            params["base_url"] = tts_config["tts_base_url"]
                        if tts_config["tts_inference_mode"] == "comfyui" and tts_config["ref_audio"]:
                            params["ref_audio"] = tts_config["ref_audio"]

                        with st.spinner("正在生成音频..."):
                            morpheus_video_studio = get_morpheus_video_studio()
                            audio_path = run_async(morpheus_video_studio.tts(**params))

                        engine_label = tts_config["tts_inference_mode"]
                        if tts_config["tts_inference_mode"] == "omnivoice" and tts_config["tts_model"]:
                            engine_label = f"omnivoice:{tts_config['tts_model']}"
                        metadata = library.save_audio_asset(
                            audio_path=audio_path,
                            title=asset_title or title or "未命名声音素材",
                            engine=engine_label,
                            voice=tts_config["tts_voice"],
                            speed=tts_config["tts_speed"],
                            content_id=content_id,
                            source_text=selected_text,
                            tags=[tag.strip() for tag in tags.split(",") if tag.strip()],
                        )
                        st.success(f"已保存声音素材：{metadata['title']}")
                        st.audio(metadata["audio_path"])
                        st.caption(metadata["audio_path"])
                    except Exception as exc:
                        st.error(f"生成音频失败：{exc}")
                        logger.exception(exc)

    st.markdown("### 声音素材库")
    if not audio_assets:
        st.caption("还没有声音素材。先生成一条 OmniVoice 或本地 TTS 旁白。")
        return

    for asset in audio_assets[:12]:
        with st.container(border=True):
            st.markdown(f"**{asset.get('title') or asset.get('asset_id')}**")
            details = [
                asset.get("engine"),
                asset.get("voice"),
                f"{asset['duration_seconds']:.1f}s" if asset.get("duration_seconds") else None,
            ]
            st.caption(" · ".join(detail for detail in details if detail))
            if asset.get("source_text_preview"):
                st.write(asset["source_text_preview"])
            audio_path = asset.get("audio_path")
            if audio_path and Path(audio_path).exists():
                st.audio(audio_path)


def _render_clone_tab(workspace: dict, library: StudioLibraryService) -> None:
    _render_omnivoice_connection(workspace)
    if not workspace["ok"]:
        return

    profiles = workspace["profiles"]
    profile_options = {
        profile["id"]: profile.get("name") or profile["id"]
        for profile in profiles
        if profile.get("id")
    }
    st.caption("这里不再负责创建克隆音色。新建、裁剪、编辑都回到 OmniVoice 原生页，这里只负责调用你已经保存好的音色。")

    prompt_col, source_col = st.columns([1.12, 0.88], gap="large")
    with prompt_col:
        with st.container(border=True):
            st.markdown("### 提示词")
            st.text_area(
                "想让这个声音说什么？",
                height=320,
                placeholder="输入想让这个声音说出的台词。",
                key="studio_clone_prompt_text",
                label_visibility="collapsed",
            )
            chip_cols = st.columns(4)
            for idx, tag in enumerate(OMNIVOICE_EXPRESSION_TAGS):
                with chip_cols[idx % 4]:
                    if st.button(tag, key=f"studio_clone_tag_{idx}", width="stretch"):
                        _append_clone_prompt_tag(tag)
            extra_cols = st.columns(4)
            with extra_cols[0]:
                if st.button("[CMU]", key="studio_clone_tag_cmu", width="stretch"):
                    _append_clone_prompt_tag("[B EY1 S]")

        with st.container(border=True):
            lang_col, step_col = st.columns([1.08, 0.92], gap="large")
            with lang_col:
                st.selectbox(
                    "语言",
                    OMNIVOICE_POPULAR_LANGUAGES,
                    index=0,
                    key="studio_clone_generation_language",
                )
            with step_col:
                st.slider(
                    "步数",
                    min_value=8,
                    max_value=64,
                    value=22,
                    step=1,
                    key="studio_clone_num_step",
                )

    with source_col:
        with st.container(border=True):
            st.markdown("### Omni 音色调用")
            selected_profile_id = None
            if not profile_options:
                st.warning("当前还没有可调用的 Omni 音色。请先去 OmniVoice 原生页创建或导入音色。")
            else:
                preferred_voice = st.session_state.get("studio_audio_preferred_omni_voice")
                profile_ids = list(profile_options.keys())
                default_index = profile_ids.index(preferred_voice) if preferred_voice in profile_ids else 0
                selected_profile_id = st.selectbox(
                    "已保存音色",
                    profile_ids,
                    index=default_index,
                    format_func=lambda profile_id: profile_options.get(profile_id, profile_id),
                    key="studio_clone_selected_profile",
                )
                st.audio(build_omnivoice_profile_audio_url(workspace["base_url"], selected_profile_id))

                action_cols = st.columns(2, gap="small")
                with action_cols[0]:
                    if st.button("设为默认配音音色", key="studio_clone_set_default_voice", width="stretch"):
                        st.session_state["studio_audio_preferred_omni_voice"] = selected_profile_id
                        st.session_state["studio_audio_omni_notice"] = f"已将 {profile_options.get(selected_profile_id, selected_profile_id)} 设为默认音色"
                        st.rerun()
                with action_cols[1]:
                    st.markdown(f"[去 OmniVoice 创建 / 编辑音色]({workspace['frontend_url']})")

                selected_profile = next((profile for profile in profiles if profile.get("id") == selected_profile_id), None)
                if selected_profile:
                    bits = [
                        selected_profile.get("language"),
                        selected_profile.get("personality"),
                        "已锁定" if selected_profile.get("is_locked") else None,
                    ]
                    if any(bits):
                        st.caption(" · ".join(bit for bit in bits if bit))
                    if selected_profile.get("instruct"):
                        st.write(selected_profile["instruct"])
                    elif selected_profile.get("ref_text"):
                        st.write(selected_profile["ref_text"][:180])

            with st.expander("高级选项", expanded=False):
                st.caption("大多数情况下保持默认即可。风格指令不是必须项，只有说话感觉明显不对时再补短标签。")
                st.text_input(
                    "风格",
                    placeholder="例如：耳语 / 男，青年 / 女，成熟",
                    key="studio_clone_generation_instruct",
                )

        with st.container(border=True):
            st.markdown("### 生成参数")
            adv_col1, adv_col2 = st.columns(2, gap="small")
            with adv_col1:
                guidance_scale = st.slider("引导强度", 1.0, 4.0, 2.0, 0.1, key="studio_clone_guidance_scale")
                speed = st.slider("语速", 0.5, 2.0, 1.0, 0.05, key="studio_clone_generation_speed")
                duration_override = st.number_input(
                    "目标时长（秒，可选）",
                    min_value=0.0,
                    value=0.0,
                    step=0.5,
                    key="studio_clone_duration_override",
                )
            with adv_col2:
                denoise = st.checkbox("参考音频降噪", value=True, key="studio_clone_denoise")
                postprocess_output = st.checkbox("输出后处理", value=True, key="studio_clone_postprocess")
                save_audio_asset = st.checkbox("保存到声音资产库", value=True, key="studio_clone_save_asset")

            generate_clicked = st.button("合成音频", type="primary", width="stretch", key="studio_clone_generate_audio")

    if generate_clicked:
        prompt_text = st.session_state.get("studio_clone_prompt_text", "").strip()
        language = st.session_state.get("studio_clone_generation_language", "Auto")
        num_step = int(st.session_state.get("studio_clone_num_step", 22))
        guidance_scale = float(st.session_state.get("studio_clone_guidance_scale", 2.0))
        speed = float(st.session_state.get("studio_clone_generation_speed", 1.0))
        duration_override = float(st.session_state.get("studio_clone_duration_override", 0.0) or 0.0)
        denoise = bool(st.session_state.get("studio_clone_denoise", True))
        postprocess_output = bool(st.session_state.get("studio_clone_postprocess", True))
        save_audio_asset = bool(st.session_state.get("studio_clone_save_asset", True))
        instruct = normalize_omnivoice_instruct(st.session_state.get("studio_clone_generation_instruct", ""))

        if not prompt_text:
            st.error("请先填写要合成的文本。")
        elif not selected_profile_id:
            st.error("请先选择一个 Omni 已保存音色。")
        else:
            generation_timeout = OMNIVOICE_TIMEOUT_READY_SECONDS
            try:
                latest_model_status = fetch_omnivoice_model_status(workspace["base_url"], timeout=4.0)
                workspace["model_status"] = latest_model_status
            except Exception as exc:
                logger.warning(f"Failed to refresh OmniVoice model status before generation: {exc}")
                latest_model_status = workspace.get("model_status") or {}

            if latest_model_status.get("status") in {"idle", "loading"} or latest_model_status.get("loading"):
                generation_timeout = OMNIVOICE_TIMEOUT_COLD_START_SECONDS

            try:
                with st.spinner("OmniVoice 正在合成音频..."):
                    generated = generate_omnivoice_audio(
                        workspace["base_url"],
                        text=prompt_text,
                        language=language,
                        instruct=instruct,
                        duration=duration_override or None,
                        num_step=num_step,
                        guidance_scale=guidance_scale,
                        speed=speed,
                        denoise=denoise,
                        postprocess_output=postprocess_output,
                        profile_id=selected_profile_id,
                        timeout=generation_timeout,
                    )
            except Exception as exc:
                try:
                    latest_model_status = fetch_omnivoice_model_status(workspace["base_url"], timeout=4.0)
                    workspace["model_status"] = latest_model_status
                except Exception as status_exc:
                    logger.warning(f"Failed to refresh OmniVoice model status after generation error: {status_exc}")
                raise exc

            try:
                audio_path = _persist_generated_audio(generated["audio_bytes"], ".wav")
                if save_audio_asset:
                    asset_title = profile_options.get(selected_profile_id or "", "") or "OmniVoice 音色调用"
                    metadata = library.save_audio_asset(
                        audio_path=audio_path,
                        title=asset_title,
                        engine="omnivoice:generate",
                        voice=selected_profile_id,
                        speed=speed,
                        source_text=prompt_text,
                        tags=["omnivoice", "voice_call"],
                    )
                    st.success(f"已保存声音素材：{metadata['title']}")
                else:
                    st.success("合成完成。")

                if generated.get("generation_time") or generated.get("audio_duration"):
                    st.caption(
                        " · ".join(
                            item
                            for item in [
                                f"生成耗时 {generated['generation_time']}s" if generated.get("generation_time") else None,
                                f"音频时长 {generated['audio_duration']}s" if generated.get("audio_duration") else None,
                                f"Seed {generated['seed']}" if generated.get("seed") else None,
                            ]
                            if item
                        )
                    )
                st.audio(generated["audio_bytes"])
                st.caption(audio_path)
            except Exception as exc:
                st.error(
                    format_omnivoice_error(
                        exc,
                        model_status=workspace.get("model_status"),
                        timeout_seconds=generation_timeout,
                    )
                )
                logger.exception(exc)

    if profiles:
        st.markdown("### 最近可调用音色")
        preview_profiles = profiles[:6]
        for profile in preview_profiles:
            with st.container(border=True):
                st.markdown(f"**{profile.get('name') or profile.get('id')}**")
                bits = [
                    profile.get("id"),
                    profile.get("language"),
                    "已锁定" if profile.get("is_locked") else None,
                ]
                st.caption(" · ".join(bit for bit in bits if bit))
                if profile.get("ref_text"):
                    st.write(profile["ref_text"][:180])
                st.audio(build_omnivoice_profile_audio_url(workspace["base_url"], profile["id"]))


def _render_design_bridge_tab(workspace: dict) -> None:
    _render_omnivoice_connection(workspace)

    design_ready = _engine_available(workspace, "voxcpm2")
    dub_ready = workspace["ok"]
    card_cols = st.columns(2, gap="large")
    with card_cols[0]:
        with st.container(border=True):
            st.markdown("### 声音设计")
            if design_ready:
                st.success("已检测到描述式音色设计引擎，可继续做原生接入。")
            else:
                st.warning("当前机器还没有可用的描述式设计引擎，先保留 OmniVoice 原生入口。")
            st.write("这部分在 OmniVoice 里依赖人格预设、设计参数和生成历史，直接复制一套到 Streamlit 成本高且容易失真。")
    with card_cols[1]:
        with st.container(border=True):
            st.markdown("### 视频配音")
            if dub_ready:
                st.success("OmniVoice 视频配音后端在线。")
            else:
                st.warning("OmniVoice 后端未连接，视频配音无法启动。")
            st.write("视频配音包含上传、转写、分段、时间轴、导出和 SSE 进度流，当前保留原生工程流更稳。")

    st.info("这里先做稳定桥接，不在 Media Studio 里仓促复制一套半成品 UI。你现在仍可在一个平台内进入 OmniVoice 原生工作台完成设计和视频配音。")
    embed = st.checkbox("在 Media Studio 内嵌打开 OmniVoice Studio", key="studio_audio_embed_omnivoice")
    if embed:
        components.iframe(workspace["frontend_url"], height=980, scrolling=True)


def _render_voice_library_tab(workspace: dict) -> None:
    _render_omnivoice_connection(workspace)
    if not workspace["ok"]:
        return

    profiles = workspace["profiles"]
    if not profiles:
        st.caption("OmniVoice 音色库还是空的。先去“声音克隆”创建一条音色。")
        return

    metric_cols = st.columns(3)
    metric_cols[0].metric("音色总数", len(profiles))
    metric_cols[1].metric("克隆音色", sum(1 for item in profiles if not item.get("instruct")))
    metric_cols[2].metric("设计音色", sum(1 for item in profiles if item.get("instruct")))

    preferred_voice = st.session_state.get("studio_audio_preferred_omni_voice")
    for profile in profiles:
        with st.container(border=True):
            top_col, action_col = st.columns([1.15, 0.85], gap="small")
            with top_col:
                title = profile.get("name") or profile.get("id")
                if preferred_voice == profile.get("id"):
                    title += " · 当前默认"
                st.markdown(f"**{title}**")
                bits = [
                    profile.get("id"),
                    profile.get("language"),
                    profile.get("personality"),
                    "已锁定" if profile.get("is_locked") else None,
                ]
                st.caption(" · ".join(bit for bit in bits if bit))
                if profile.get("instruct"):
                    st.write(profile["instruct"])
                elif profile.get("ref_text"):
                    st.write(profile["ref_text"][:180])
                st.audio(build_omnivoice_profile_audio_url(workspace["base_url"], profile["id"]))
            with action_col:
                if st.button("用于配音", key=f"studio_use_profile_{profile['id']}", width="stretch"):
                    st.session_state["studio_audio_preferred_omni_voice"] = profile["id"]
                    st.session_state["studio_audio_omni_notice"] = f"已将 {profile.get('name') or profile['id']} 设为当前默认音色"
                    st.rerun()
                if st.button("删除音色", key=f"studio_delete_profile_{profile['id']}", width="stretch"):
                    try:
                        delete_omnivoice_profile(workspace["base_url"], profile["id"])
                        if st.session_state.get("studio_audio_preferred_omni_voice") == profile["id"]:
                            st.session_state.pop("studio_audio_preferred_omni_voice", None)
                        st.session_state["studio_audio_omni_notice"] = f"已删除音色：{profile.get('name') or profile['id']}"
                        st.rerun()
                    except Exception as exc:
                        st.error(format_omnivoice_error(exc))
                        logger.exception(exc)


def _render_transcription_result(library: StudioLibraryService) -> None:
    result = st.session_state.get("studio_audio_transcription_result")
    if not result:
        return

    st.markdown("### 转写结果")
    if result.get("text"):
        st.text_area("文本", value=result["text"], height=240)
    else:
        st.text_area("输出", value=result.get("raw_output", ""), height=240)

    if result.get("segments"):
        st.dataframe(result["segments"], width="stretch")

    download_name = result.get("download_name", "transcription.txt")
    raw_output = result.get("raw_output") or result.get("text") or ""
    st.download_button(
        "下载结果",
        raw_output,
        file_name=download_name,
        mime=result.get("mime", "text/plain"),
        width="stretch",
    )

    if result.get("text"):
        save_title = st.text_input(
            "保存到内容库的标题",
            value=result.get("title", "音频转写"),
            key="studio_audio_transcript_title",
        )
        if st.button("保存到内容库", key="studio_audio_save_transcript", width="stretch"):
            metadata = library.create_text_item(
                title=save_title,
                text=result["text"],
                content_type="transcript",
                tags=["transcript", "omnivoice"],
            )
            st.success(f"已写入内容库：{metadata['title']}")


def _render_transcription_tab(workspace: dict, library: StudioLibraryService) -> None:
    _render_omnivoice_connection(workspace)
    if not workspace["ok"]:
        return

    with st.form("studio_audio_transcription_form"):
        left_col, right_col = st.columns([1.05, 0.95], gap="large")
        with left_col:
            media_file = st.file_uploader(
                "上传音频或视频",
                type=["wav", "mp3", "m4a", "aac", "ogg", "flac", "webm", "mp4", "mov", "mkv"],
                key="studio_audio_transcribe_upload",
            )
            prompt = st.text_area(
                "提示词（可选）",
                height=100,
                placeholder="如果你想让转写更贴近某类术语或上文风格，可以补一句提示。",
                key="studio_audio_transcribe_prompt",
            )
        with right_col:
            response_format = st.selectbox(
                "输出格式",
                ["verbose_json", "json", "text", "srt", "vtt"],
                index=0,
                key="studio_audio_transcribe_format",
            )
            language = st.text_input(
                "语言（可选）",
                placeholder="例如 zh / en / ja",
                key="studio_audio_transcribe_language",
            )
            title = st.text_input(
                "结果标题",
                value="音频转写",
                key="studio_audio_transcribe_title",
            )
        submitted = st.form_submit_button("开始转写", type="primary")

    if submitted:
        if media_file is None:
            st.error("请先上传音频或视频文件。")
        else:
            try:
                with st.spinner("OmniVoice 正在转写..."):
                    output = create_omnivoice_transcription(
                        workspace["base_url"],
                        filename=media_file.name,
                        content=media_file.getvalue(),
                        language=language.strip() or None,
                        prompt=prompt.strip() or None,
                        response_format=response_format,
                    )

                if isinstance(output, dict):
                    text = output.get("text", "")
                    segments = output.get("segments", [])
                    raw_output = json.dumps(output, ensure_ascii=False, indent=2)
                    mime = "application/json" if response_format in {"json", "verbose_json"} else "text/plain"
                else:
                    text = output if response_format == "text" else ""
                    segments = []
                    raw_output = output
                    mime = "text/vtt" if response_format == "vtt" else "text/plain"

                suffix_map = {
                    "verbose_json": ".json",
                    "json": ".json",
                    "text": ".txt",
                    "srt": ".srt",
                    "vtt": ".vtt",
                }
                stem = Path(media_file.name).stem
                st.session_state["studio_audio_transcription_result"] = {
                    "title": title.strip() or stem,
                    "text": text,
                    "segments": segments,
                    "raw_output": raw_output,
                    "mime": mime,
                    "download_name": f"{stem}{suffix_map.get(response_format, '.txt')}",
                }
                st.success("转写完成。")
            except Exception as exc:
                st.error(format_omnivoice_error(exc))
                logger.exception(exc)

    _render_transcription_result(library)


def main():
    init_session_state()
    init_i18n()
    inject_studio_css()
    render_faq_sidebar()
    render_studio_hero(
        "音频工坊",
        "把内容快速变成可复用的声音资产，并把 OmniVoice 的音色调用、音色库、转写能力收进同一个工作台。",
        kicker="Audio Workshop",
    )

    library = StudioLibraryService()
    audio_assets = library.list_audio_assets()
    content_items = library.list_content_items()
    omni_workspace = _get_omnivoice_workspace()

    render_workspace_context(
        [
            ("OmniVoice", "在线" if omni_workspace["ok"] else "离线", omni_workspace["status"]),
            ("Content Items", str(len(content_items)) if content_items else "", "内容库里的文本可直接送入配音和转写"),
            ("Audio Assets", str(len(audio_assets)) if audio_assets else "", "生成完成后会自动沉淀到声音资产库"),
        ],
        note="音频工坊现在分成五块：配音、Omni 音色调用、设计/视频配音桥接、音色库、转写。",
    )
    _show_omnivoice_notice()

    tab_labels = ["🎙️ 配音", "🎚️ Omni 音色", "🎛️ 设计 / 视频配音", "🗃️ 音色库", "📝 转写"]
    if hasattr(st, "segmented_control"):
        active_tab = st.segmented_control(
            "音频工坊模块",
            options=tab_labels,
            default=tab_labels[0],
            key="studio_audio_active_tab",
            label_visibility="collapsed",
        )
    else:
        active_tab = st.radio(
            "音频工坊模块",
            options=tab_labels,
            horizontal=True,
            key="studio_audio_active_tab_fallback",
            label_visibility="collapsed",
        )

    if active_tab == "🎙️ 配音":
        _render_dubbing_tab(library, omni_workspace)
    elif active_tab == "🎚️ Omni 音色":
        _render_clone_tab(omni_workspace, library)
    elif active_tab == "🎛️ 设计 / 视频配音":
        _render_design_bridge_tab(omni_workspace)
    elif active_tab == "🗃️ 音色库":
        _render_voice_library_tab(omni_workspace)
    else:
        _render_transcription_tab(omni_workspace, library)


if __name__ == "__main__":
    main()
