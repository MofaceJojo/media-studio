import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from morpheus_video_studio.services.studio_library import StudioLibraryService
from web.components.faq import render_faq_sidebar
from web.components.studio_shell import (
    inject_studio_css,
    render_core_action,
    render_studio_hero,
)
from web.state.session import init_i18n, init_session_state


def main() -> None:
    init_session_state()
    init_i18n()
    inject_studio_css()
    render_faq_sidebar()

    render_studio_hero(
        "今天想创作什么？",
        "从内容、声音、视频或数字人口播开始，创作结果会自动沉淀到工具栏中的资产与项目。",
        kicker="Morpheus Video Studio",
    )

    st.markdown("### 核心创作")
    first_row = st.columns(2, gap="large")
    with first_row[0]:
        render_core_action(
            "内容创作",
            "整理主题、文案、PDF 和书摘，建立后续创作需要的内容。",
            "pages/2_📚_Content_Library.py",
            "01",
        )
    with first_row[1]:
        render_core_action(
            "音频创作",
            "生成旁白、选择音色，并保存可重复使用的声音资产。",
            "pages/3_🎙️_Audio_Workshop.py",
            "02",
        )

    second_row = st.columns(2, gap="large")
    with second_row[0]:
        render_core_action(
            "视频创作",
            "从主题、文档或现有素材快速生成完整视频。",
            "pages/4_🎬_Video_Workshop.py",
            "03",
        )
    with second_row[1]:
        render_core_action(
            "数字人口播",
            "组合形象和声音，制作讲解、主持与口播内容。",
            "pages/5_🤖_Digital_Human.py",
            "04",
        )

    st.markdown("### 继续创作")
    video_assets = StudioLibraryService().list_video_assets()
    if not video_assets:
        with st.container(border=True):
            st.markdown("**还没有视频项目**")
            st.caption("选择一个主题开始，完成后可以从左侧工具栏继续查看和管理。")
            st.page_link(
                "pages/4_🎬_Video_Workshop.py",
                label="开始视频创作",
                width="stretch",
            )
        return

    latest = video_assets[0]
    with st.container(border=True):
        st.markdown(f"**{latest.get('title') or latest.get('asset_id')}**")
        details = [
            latest.get("status") or "已生成",
            f"{latest['duration']:.1f} 秒" if latest.get("duration") else None,
            f"{latest['n_frames']} 个镜头" if latest.get("n_frames") else None,
        ]
        st.caption(" · ".join(str(item) for item in details if item))
        if latest.get("source_text_preview"):
            st.write(latest["source_text_preview"])
        st.page_link(
            "pages/2_📚_History.py",
            label="查看视频项目",
            width="stretch",
        )


if __name__ == "__main__":
    main()
