from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from morpheus_video_studio.config import config_manager
from morpheus_video_studio.utils.omnivoice_util import (
    check_omnivoice_health,
    normalize_omnivoice_instruct,
)


LOCAL_VOICE_STATE_KEY = "studio_audio_preferred_local_voice"
LOCAL_SPEED_STATE_KEY = "studio_audio_preferred_local_speed"
OMNI_VOICE_STATE_KEY = "studio_audio_preferred_omni_voice"
OMNI_SPEED_STATE_KEY = "studio_audio_preferred_omni_speed"
OMNI_MODEL_STATE_KEY = "studio_audio_preferred_omni_model"
OMNI_INSTRUCT_STATE_KEY = "studio_audio_preferred_omni_instruct"


def _get_state(state: MutableMapping[str, Any] | None = None) -> MutableMapping[str, Any]:
    return state if state is not None else st.session_state


def _value_or_default(state: MutableMapping[str, Any], key: str, default: Any) -> Any:
    value = state.get(key)
    if value is None or value == "":
        return default
    return value


def get_local_tts_preferences(
    saved_voice: str,
    saved_speed: float,
    *,
    state: MutableMapping[str, Any] | None = None,
) -> tuple[str, float]:
    session_state = _get_state(state)
    voice = str(_value_or_default(session_state, LOCAL_VOICE_STATE_KEY, saved_voice))
    speed = float(_value_or_default(session_state, LOCAL_SPEED_STATE_KEY, saved_speed))
    return voice, speed


def get_omnivoice_tts_preferences(
    saved_voice: str,
    saved_speed: float,
    saved_model: str,
    saved_instruct: str,
    *,
    state: MutableMapping[str, Any] | None = None,
) -> tuple[str, float, str, str]:
    session_state = _get_state(state)
    voice = str(_value_or_default(session_state, OMNI_VOICE_STATE_KEY, saved_voice))
    speed = float(_value_or_default(session_state, OMNI_SPEED_STATE_KEY, saved_speed))
    model = str(_value_or_default(session_state, OMNI_MODEL_STATE_KEY, saved_model))
    instruct = normalize_omnivoice_instruct(
        _value_or_default(session_state, OMNI_INSTRUCT_STATE_KEY, saved_instruct)
    ) or saved_instruct
    return voice, speed, model, instruct


def persist_local_tts_preferences(
    voice: str,
    speed: float,
    *,
    state: MutableMapping[str, Any] | None = None,
    manager=config_manager,
) -> None:
    session_state = _get_state(state)
    session_state[LOCAL_VOICE_STATE_KEY] = voice
    session_state[LOCAL_SPEED_STATE_KEY] = float(speed)

    current = manager.get_comfyui_config()["tts"]["local"]
    if current.get("voice") == voice and float(current.get("speed", 1.2)) == float(speed):
        return

    manager.update(
        {
            "comfyui": {
                "tts": {
                    "local": {
                        "voice": voice,
                        "speed": float(speed),
                    }
                }
            }
        }
    )
    manager.save()


def persist_omnivoice_tts_preferences(
    voice: str,
    speed: float,
    *,
    model: str | None = None,
    instruct: str | None = None,
    state: MutableMapping[str, Any] | None = None,
    manager=config_manager,
) -> None:
    session_state = _get_state(state)
    session_state[OMNI_VOICE_STATE_KEY] = voice
    session_state[OMNI_SPEED_STATE_KEY] = float(speed)
    if model:
        session_state[OMNI_MODEL_STATE_KEY] = model
    if instruct:
        session_state[OMNI_INSTRUCT_STATE_KEY] = normalize_omnivoice_instruct(instruct) or instruct

    current = manager.get_comfyui_config()["tts"]["omnivoice"]
    normalized_instruct = normalize_omnivoice_instruct(instruct) if instruct else current.get("instruct")
    updates: dict[str, Any] = {}

    if current.get("voice") != voice:
        updates["voice"] = voice
    if float(current.get("speed", 1.0)) != float(speed):
        updates["speed"] = float(speed)
    if model and current.get("model") != model:
        updates["model"] = model
    if normalized_instruct and current.get("instruct") != normalized_instruct:
        updates["instruct"] = normalized_instruct

    if not updates:
        return

    manager.update({"comfyui": {"tts": {"omnivoice": updates}}})
    manager.save()


def fetch_omnivoice_voice_catalog(base_url: str) -> tuple[list[str], list[str]]:
    """Return (voice_ids, display_labels) from a running OmniVoice, or a
    small built-in fallback when it can't be reached."""
    voice_items: list[dict] = []
    try:
        import httpx

        with httpx.Client(timeout=2.5, trust_env=False) as client:
            resp = client.get(f"{base_url}/v1/audio/voices")
            resp.raise_for_status()
            voice_items = resp.json().get("voices", [])
    except Exception:
        voice_items = []

    voice_ids = [item.get("voice_id") for item in voice_items if item.get("voice_id")]
    labels = [
        f"{item.get('name') or item.get('voice_id')} ({item.get('voice_id')})"
        for item in voice_items
        if item.get("voice_id")
    ]
    if not voice_ids:
        voice_ids = ["default", "alloy", "nova", "demo0001"]
        labels = ["Default", "Alloy", "Nova", "OmniVoice Demo"]
    return voice_ids, labels


def render_tts_config(morpheus_video_studio, *, key_prefix: str) -> dict[str, Any]:
    """Render a self-contained TTS configuration block (Edge local + OmniVoice)
    and return the generation params. Shared so every workshop offers the same
    voice choices instead of hard-coding Edge-only.

    Returns keys: tts_inference_mode, voice_id, tts_speed, tts_instruct.
    """
    from morpheus_video_studio.tts_voices import EDGE_TTS_VOICES, get_voice_display_name

    from web.i18n import get_language, tr

    comfyui_config = config_manager.get_comfyui_config()
    tts_config = comfyui_config.get("tts", {})
    saved_mode = tts_config.get("inference_mode", "local")

    mode = st.radio(
        tr("tts.inference_mode"),
        ["local", "omnivoice"],
        format_func=lambda x: "OmniVoice 本地" if x == "omnivoice" else tr("tts.mode.local"),
        index=1 if saved_mode == "omnivoice" else 0,
        horizontal=True,
        key=f"{key_prefix}_tts_mode",
    )

    tts_instruct: str | None = None

    if mode == "local":
        local_config = tts_config.get("local", {})
        saved_voice, saved_speed = get_local_tts_preferences(
            local_config.get("voice", "zh-CN-YunjianNeural"),
            float(local_config.get("speed", 1.2)),
        )
        voice_options, voice_ids, default_index = [], [], 0
        for idx, vc in enumerate(EDGE_TTS_VOICES):
            vid = vc["id"]
            voice_options.append(get_voice_display_name(vid, tr, get_language()))
            voice_ids.append(vid)
            if vid == saved_voice:
                default_index = idx

        voice_col, speed_col = st.columns([1, 1])
        with voice_col:
            picked = st.selectbox(
                tr("tts.voice_selector"), voice_options, index=default_index,
                key=f"{key_prefix}_local_voice",
            )
            voice_id = voice_ids[voice_options.index(picked)]
        with speed_col:
            tts_speed = st.slider(
                tr("tts.speed"), min_value=0.5, max_value=2.0, value=saved_speed,
                step=0.1, format="%.1fx", key=f"{key_prefix}_local_speed",
            )
        persist_local_tts_preferences(voice_id, tts_speed)
        return {
            "tts_inference_mode": "local",
            "voice_id": voice_id,
            "tts_speed": tts_speed,
            "tts_instruct": None,
        }

    # OmniVoice
    omni_config = tts_config.get("omnivoice", {})
    base_url = omni_config.get("base_url", "http://127.0.0.1:3900").rstrip("/")
    saved_voice, saved_speed, _, saved_instruct = get_omnivoice_tts_preferences(
        omni_config.get("voice", "default"),
        float(omni_config.get("speed", 1.0)),
        omni_config.get("model", "omnivoice"),
        normalize_omnivoice_instruct(omni_config.get("instruct")) or "男，青年",
    )

    omni_ok, omni_status = check_omnivoice_health(base_url)
    (st.success if omni_ok else st.warning)(omni_status)

    voice_ids, voice_labels = fetch_omnivoice_voice_catalog(base_url)
    default_index = voice_ids.index(saved_voice) if saved_voice in voice_ids else 0

    voice_col, speed_col = st.columns([1, 1])
    with voice_col:
        picked = st.selectbox(
            tr("tts.voice_selector"), voice_labels, index=default_index,
            key=f"{key_prefix}_omni_voice",
        )
        voice_id = voice_ids[voice_labels.index(picked)]
    with speed_col:
        tts_speed = st.slider(
            tr("tts.speed"), min_value=0.5, max_value=2.0, value=float(saved_speed),
            step=0.1, format="%.1fx", key=f"{key_prefix}_omni_speed",
        )
    tts_instruct = st.text_input(
        "OmniVoice 风格指令", value=saved_instruct, key=f"{key_prefix}_omni_instruct",
        help="仅支持预设标签，例如：男，青年 / female, young adult。",
    )
    tts_instruct = normalize_omnivoice_instruct(tts_instruct) or "男，青年"
    persist_omnivoice_tts_preferences(voice_id, tts_speed, instruct=tts_instruct)
    return {
        "tts_inference_mode": "omnivoice",
        "voice_id": voice_id,
        "tts_speed": tts_speed,
        "tts_instruct": tts_instruct,
    }
