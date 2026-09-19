"""Application navigation and the low-frequency tool drawer."""

from __future__ import annotations

from typing import Final

import streamlit as st


CORE_PAGE_SPECS: Final[tuple[dict[str, object], ...]] = (
    {"path": "pages/1_🏠_Studio.py", "label": "工作台", "icon": "🏠", "default": True},
    {"path": "pages/2_📚_Content_Library.py", "label": "内容创作", "icon": "📝"},
    {"path": "pages/3_🎙️_Audio_Workshop.py", "label": "音频创作", "icon": "🎙️"},
    {"path": "pages/4_🎬_Video_Workshop.py", "label": "视频创作", "icon": "🎬"},
    {"path": "pages/5_🤖_Digital_Human.py", "label": "数字人口播", "icon": "🤖"},
)

TOOL_PAGE_SPECS: Final[tuple[dict[str, object], ...]] = (
    {"path": "pages/6_🗂️_Asset_Library.py", "label": "已有资产", "icon": "🗃️"},
    {"path": "pages/2_📚_History.py", "label": "视频项目", "icon": "🎞️"},
    {"path": "pages/7_⚙️_Settings.py", "label": "系统设置", "icon": "⚙️"},
)


def build_streamlit_pages() -> list[st.Page]:
    """Register every page while keeping the built-in page list hidden."""
    return [
        st.Page(
            str(spec["path"]),
            title=str(spec["label"]),
            icon=str(spec["icon"]),
            default=bool(spec.get("default", False)),
        )
        for spec in (*CORE_PAGE_SPECS, *TOOL_PAGE_SPECS)
    ]


def render_tool_drawer() -> None:
    """Render only the home return and low-frequency management tools."""
    with st.sidebar:
        st.markdown("#### Morpheus")
        st.caption("创作工具")
        st.page_link(
            str(CORE_PAGE_SPECS[0]["path"]),
            label="返回工作台",
            icon=str(CORE_PAGE_SPECS[0]["icon"]),
        )
        st.divider()
        st.caption("管理")
        for spec in TOOL_PAGE_SPECS:
            st.page_link(
                str(spec["path"]),
                label=str(spec["label"]),
                icon=str(spec["icon"]),
            )
