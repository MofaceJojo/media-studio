from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

import streamlit as st

from morpheus_video_studio.config import config_manager
from morpheus_video_studio.utils.omnivoice_util import normalize_omnivoice_instruct


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
