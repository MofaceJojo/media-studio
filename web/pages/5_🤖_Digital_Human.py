import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from morpheus_video_studio.services.studio_library import StudioLibraryService
from web.components.faq import render_faq_sidebar
from web.components.studio_shell import inject_studio_css, render_studio_hero, render_workspace_context
from web.pipelines import get_pipeline_ui
from web.state.session import get_morpheus_video_studio, init_i18n, init_session_state


def main():
    init_session_state()
    init_i18n()
    inject_studio_css()
    render_faq_sidebar()
    render_studio_hero(
        "数字人口播",
        "轻二维口播模块。适合讲解、格言、路线和内容解读，用人物立绘、配音和简单张嘴做出有表达感的视频。",
        kicker="Digital Human",
    )

    library = StudioLibraryService()
    selected_content_id = st.session_state.get("studio_selected_content_id")
    selected_item = library.get_content_item(selected_content_id) if selected_content_id else None
    selected_audio_path = st.session_state.get("studio_selected_audio_asset_path")
    selected_audio = (
        str(Path(selected_audio_path).resolve())
        if selected_audio_path and Path(selected_audio_path).exists()
        else None
    )

    render_workspace_context(
        [
            (
                "Selected Content",
                selected_item.get("title") if selected_item else "",
                selected_item.get("content_type") if selected_item else None,
            ),
            (
                "Voice Reference",
                Path(selected_audio).name if selected_audio else "",
                "ComfyUI TTS 会直接使用这条声音资产",
            ),
        ],
        note="这里更适合把内容库里的文本和音频变成轻量角色口播，而不是走重型数字人链路。",
    )

    if selected_item or selected_audio:
        with st.container(border=True):
            st.markdown("### 当前复用上下文")
            if selected_item:
                st.markdown(f"**内容**：{selected_item.get('title') or selected_item.get('content_id')}")
                st.caption(
                    " · ".join(
                        part
                        for part in [
                            selected_item.get("content_type"),
                            f"{selected_item.get('char_count', 0)} 字",
                            selected_item.get("source_filename"),
                        ]
                        if part
                    )
                )
                if selected_item.get("summary"):
                    st.write(selected_item["summary"])
            if selected_audio:
                st.markdown(f"**声音参考**：{Path(selected_audio).name}")
                st.audio(selected_audio)
                st.caption("切到 ComfyUI 合成时，会自动把这条声音资产作为参考音频带入。")

    pipeline = get_pipeline_ui("digital_human")
    if pipeline is None:
        st.error("没有找到数字人口播工作流入口。")
        return

    morpheus_video_studio = get_morpheus_video_studio()
    if pipeline.description:
        st.caption(pipeline.description)
    pipeline.render(morpheus_video_studio)


if __name__ == "__main__":
    main()
