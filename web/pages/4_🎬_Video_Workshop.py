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


def _render_pipeline(name: str, morpheus_video_studio) -> None:
    pipeline = get_pipeline_ui(name)
    if pipeline is None:
        st.error(f"工作流未找到：{name}")
        return
    if pipeline.description:
        st.caption(pipeline.description)
    pipeline.render(morpheus_video_studio)


def main():
    init_session_state()
    init_i18n()
    inject_studio_css()
    render_faq_sidebar()
    render_studio_hero(
        "视频工坊",
        "把视频创作收束成几个清楚的入口。优先使用快速创作、文档转视频和自定义素材，其它能力放进高级工具区。",
        kicker="Media Studio",
    )

    library = StudioLibraryService()
    selected_content_id = st.session_state.get("studio_selected_content_id")
    selected_item = library.get_content_item(selected_content_id) if selected_content_id else None
    selected_assets = [
        str(Path(path).resolve())
        for path in (st.session_state.get("studio_selected_asset_paths") or [])
        if path and Path(path).exists()
    ]
    render_workspace_context(
        [
            (
                "Selected Content",
                selected_item.get("title") if selected_item else "",
                selected_item.get("content_type") if selected_item else None,
            ),
            (
                "Preloaded Assets",
                f"{len(selected_assets)} 项" if selected_assets else "",
                "会直接带入自定义素材工作区",
            ),
            (
                "Recommended Path",
                "文档转视频" if selected_item and selected_item.get("source_kind") == "document" else "",
                "检测到文档来源，建议优先走文档转视频",
            ),
        ],
        note="视频工坊只保留少数清晰入口。默认先判断内容类型，再决定走快速创作、文档转视频或自定义素材。",
    )
    morpheus_video_studio = get_morpheus_video_studio()

    if selected_item:
        with st.container(border=True):
            st.markdown("### 当前带入内容")
            st.markdown(f"**{selected_item.get('title') or selected_item.get('content_id')}**")
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
            st.info("文档或长内容建议优先使用“绘本文档自动视频”；短文案、格言和主题类内容建议优先使用“快速创作”。")
            quick_col, doc_col = st.columns(2)
            is_document = (
                selected_item.get("source_kind") == "document"
                and selected_item.get("source_path")
                and Path(selected_item["source_path"]).exists()
            )
            with quick_col:
                if st.button("带入快速创作", width="stretch", key="apply_selected_to_quick_create"):
                    st.session_state["studio_applied_content_to_quick_create"] = None
                    st.session_state["studio_video_workshop_section"] = "quick_create"
                    st.success("已准备把当前内容带入快速创作。切到“快速创作”即可看到预填文本。")
            with doc_col:
                if is_document:
                    st.success("当前条目带有原始文档文件，切到“文档转视频”时会自动使用它。")
                else:
                    st.caption("当前条目不是文档导入项，文档转视频不会自动带入原始文件。")

    if selected_assets:
        with st.container(border=True):
            st.markdown("### 当前预加载素材")
            st.caption(f"已从资产库带入 {len(selected_assets)} 个素材。切到“自定义素材”即可直接生成或继续补充上传。")
            for path in selected_assets[:3]:
                st.write(Path(path).name)
    if "studio_video_workshop_section" not in st.session_state:
        if selected_assets:
            st.session_state["studio_video_workshop_section"] = "custom_media"
        elif selected_item and selected_item.get("source_kind") == "document":
            st.session_state["studio_video_workshop_section"] = "book_pdf_video"
        else:
            st.session_state["studio_video_workshop_section"] = "quick_create"

    section = st.radio(
        "视频工坊工作区",
        ["quick_create", "book_pdf_video", "custom_media", "advanced"],
        horizontal=True,
        label_visibility="collapsed",
        key="studio_video_workshop_section",
        format_func=lambda value: {
            "quick_create": "⚡ 快速创作",
            "book_pdf_video": "📖 文档转视频",
            "custom_media": "🎞️ 自定义素材",
            "advanced": "🧰 高级工具",
        }[value],
    )

    if section == "quick_create":
        _render_pipeline("quick_create", morpheus_video_studio)
    elif section == "book_pdf_video":
        _render_pipeline("book_pdf_video", morpheus_video_studio)
    elif section == "custom_media":
        _render_pipeline("custom_media", morpheus_video_studio)
    else:
        st.caption("这里保留更专业或更偏实验性的能力，不占据默认主路径。")
        if "studio_video_advanced_section" not in st.session_state:
            st.session_state["studio_video_advanced_section"] = "image_to_video"
        advanced_section = st.radio(
            "高级工具",
            [
                "image_to_video",
                "stock_materials",
                "video_mix",
                "video_merge",
                "action_transfer",
            ],
            horizontal=True,
            label_visibility="collapsed",
            key="studio_video_advanced_section",
            format_func=lambda value: {
                "image_to_video": "🎥 图生视频",
                "stock_materials": "🎞️ 素材库",
                "video_mix": "🎬 视频混剪",
                "video_merge": "🧩 合并视频",
                "action_transfer": "💃 动作迁移",
            }[value],
        )
        _render_pipeline(advanced_section, morpheus_video_studio)


if __name__ == "__main__":
    main()
