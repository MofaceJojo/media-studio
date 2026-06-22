from __future__ import annotations

import streamlit as st

from morpheus_video_studio.style_presets import get_image_style_preset, list_image_style_presets


def get_default_image_style_preset() -> dict[str, str]:
    presets = list_image_style_presets()
    if not presets:
        raise ValueError("No image style presets configured")
    return presets[0]


def render_image_style_preset_picker(*, session_key: str = "image_style_preset") -> dict | None:
    presets = list_image_style_presets()
    preset_labels = {preset["label"]: preset["id"] for preset in presets}
    labels = list(preset_labels.keys())
    default_preset = get_default_image_style_preset()

    if session_key not in st.session_state or st.session_state.get(session_key) not in preset_labels:
        st.session_state[session_key] = default_preset["label"]

    if hasattr(st, "pills"):
        selected_label = st.pills("风格标签", labels, key=session_key)
    else:
        selected_label = st.radio("风格标签", labels, horizontal=True, key=session_key)

    selected_label = selected_label or st.session_state[session_key]
    return get_image_style_preset(preset_labels[selected_label])
