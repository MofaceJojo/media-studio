from __future__ import annotations

import streamlit as st

from morpheus_video_studio.style_presets import get_image_style_preset, list_image_style_presets


def render_image_style_preset_picker(*, session_key: str = "image_style_preset") -> dict | None:
    presets = list_image_style_presets()
    preset_labels = {preset["label"]: preset["id"] for preset in presets}
    labels = list(preset_labels.keys())

    if hasattr(st, "pills"):
        selected_label = st.pills("风格标签", labels, key=session_key)
    else:
        selected_label = st.radio("风格标签", labels, horizontal=True, key=session_key)

    if not selected_label:
        return None
    return get_image_style_preset(preset_labels[selected_label])
