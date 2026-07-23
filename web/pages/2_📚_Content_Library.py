import sys
import uuid
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from morpheus_video_studio.services.studio_library import StudioLibraryService
from morpheus_video_studio.utils.document_text import extract_text_from_document
from web.components.faq import render_faq_sidebar
from web.components.studio_shell import inject_studio_css, render_studio_hero, render_workspace_context
from web.state.session import init_i18n, init_session_state


CONTENT_TYPES = ["书籍", "生活格言", "旅游路线", "脚本", "资料整理"]


def _save_uploaded_file(uploaded_file) -> Path:
    upload_dir = Path("temp/content_library_uploads") / st.session_state.get(
        "content_library_upload_id", uuid.uuid4().hex[:12]
    )
    st.session_state.content_library_upload_id = upload_dir.name
    upload_dir.mkdir(parents=True, exist_ok=True)
    output = upload_dir / uploaded_file.name
    output.write_bytes(uploaded_file.getbuffer())
    return output


def _set_selected_content(content_id: str) -> None:
    st.session_state["studio_selected_content_id"] = content_id


def _reset_text_form() -> None:
    st.session_state["studio_text_title"] = ""
    st.session_state["studio_text_type"] = CONTENT_TYPES[0]
    st.session_state["studio_text_tags"] = ""
    st.session_state["studio_text_body"] = ""


def main():
    init_session_state()
    init_i18n()
    inject_studio_css()
    render_faq_sidebar()
    render_studio_hero(
        "内容库",
        "把 PDF、Word、TXT、路线和格言沉淀成长期可复用的内容资产。后续音频工坊、视频工坊和数字人口播都会从这里取内容。",
        kicker="Content Library",
    )

    library = StudioLibraryService()
    selected_content_id = st.session_state.get("studio_selected_content_id")
    selected_item = library.get_content_item(selected_content_id) if selected_content_id else None

    render_workspace_context(
        [
            (
                "Selected Content",
                selected_item.get("title") if selected_item else "",
                selected_item.get("content_type") if selected_item else None,
            ),
            (
                "Document Source",
                selected_item.get("source_filename") if selected_item else "",
                "文档条目可以直接带入文档转视频",
            ),
        ],
        note="内容库是所有后续模块的起点。选中过的内容会被音频工坊、视频工坊和数字人口播持续复用。",
    )

    import_col, library_col = st.columns([1, 1], gap="large")
    with import_col:
        with st.container(border=True):
            st.markdown("### 导入文档")
            uploaded = st.file_uploader(
                "导入 PDF / Word / PPT / TXT / Markdown",
                type=["pdf", "docx", "doc", "pptx", "ppt", "txt", "md", "markdown", "csv"],
                key="studio_content_upload",
            )
            upload_title = st.text_input("内容标题", key="studio_content_upload_title")
            upload_type = st.selectbox("内容类型", CONTENT_TYPES, key="studio_content_upload_type")
            upload_tags = st.text_input("标签（逗号分隔）", key="studio_content_upload_tags")

            if uploaded:
                temp_path = _save_uploaded_file(uploaded)
                try:
                    extracted_text = extract_text_from_document(temp_path, max_chars=24000)
                    st.success(f"已提取 {len(extracted_text)} 字")
                    with st.expander("预览提取内容", expanded=False):
                        st.text_area("提取文本", value=extracted_text, height=260)
                    if st.button("保存到内容库", key="studio_save_uploaded_content", width="stretch"):
                        metadata = library.import_document(
                            source_path=temp_path,
                            extracted_text=extracted_text,
                            content_type=upload_type,
                            title=upload_title or temp_path.stem,
                            tags=[tag.strip() for tag in upload_tags.split(",") if tag.strip()],
                        )
                        _set_selected_content(metadata["content_id"])
                        st.success(f"已保存：{metadata['title']}")
                        st.rerun()
                except Exception as exc:
                    st.error(f"提取文档失败：{exc}")

        with st.container(border=True):
            st.markdown("### 直接录入")
            text_title = st.text_input("文本标题", key="studio_text_title")
            text_type = st.selectbox("文本类型", CONTENT_TYPES, key="studio_text_type")
            text_tags = st.text_input("标签（逗号分隔）", key="studio_text_tags")
            text_body = st.text_area(
                "正文",
                height=260,
                placeholder="例如：一组生活格言、一本书的摘要、一次旅行路线规划、一个视频脚本。",
                key="studio_text_body",
            )
            if st.button("保存文本到内容库", key="studio_save_text_content", width="stretch"):
                if not text_body.strip():
                    st.error("请先输入正文。")
                else:
                    metadata = library.create_text_item(
                        title=text_title or "未命名内容",
                        text=text_body,
                        content_type=text_type,
                        tags=[tag.strip() for tag in text_tags.split(",") if tag.strip()],
                    )
                    _set_selected_content(metadata["content_id"])
                    _reset_text_form()
                    st.success(f"已保存：{metadata['title']}")
                    st.rerun()

    with library_col:
        st.markdown("### 库内内容")
        query = st.text_input("搜索标题或摘要", key="studio_content_query")
        items = library.list_content_items()
        if query.strip():
            lowered = query.lower().strip()
            items = [
                item
                for item in items
                if lowered in (item.get("title", "") + " " + item.get("summary", "")).lower()
            ]

        if not items:
            st.caption("内容库还没有资产。先导入一本 PDF 或一组文本。")
        for item in items:
            with st.container(border=True):
                st.markdown(f"**{item.get('title') or item.get('content_id')}**")
                st.caption(
                    " · ".join(
                        part
                        for part in [
                            item.get("content_type"),
                            f"{item.get('char_count', 0)} 字",
                            item.get("source_filename"),
                        ]
                        if part
                    )
                )
                if item.get("summary"):
                    st.write(item["summary"])
                content_id = item["content_id"]
                audio_col, video_col, link_col = st.columns([0.34, 0.33, 0.33])
                with audio_col:
                    if st.button("送到音频工坊", key=f"to_audio_{content_id}", width="stretch"):
                        _set_selected_content(content_id)
                        st.switch_page("pages/3_🎙️_Audio_Workshop.py")
                with video_col:
                    if st.button("送到视频工坊", key=f"to_video_{content_id}", width="stretch"):
                        _set_selected_content(content_id)
                        st.session_state["studio_video_workshop_section"] = (
                            "book_pdf_video" if item.get("source_kind") == "document" else "quick_create"
                        )
                        st.switch_page("pages/4_🎬_Video_Workshop.py")
                with link_col:
                    st.page_link("pages/3_🎙️_Audio_Workshop.py", label="打开音频工坊", width="stretch")


if __name__ == "__main__":
    main()
