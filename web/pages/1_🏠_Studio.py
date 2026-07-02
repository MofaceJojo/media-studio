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
    render_metric_cards,
    render_module_cards,
    render_studio_hero,
    render_workspace_context,
)
from web.state.session import init_i18n, init_session_state


def main():
    init_session_state()
    init_i18n()
    inject_studio_css()
    render_faq_sidebar()

    library = StudioLibraryService()
    content_items = library.list_content_items()
    audio_assets = library.list_audio_assets()
    video_assets = library.list_video_assets()
    selected_content_id = st.session_state.get("studio_selected_content_id")
    selected_content = library.get_content_item(selected_content_id) if selected_content_id else None
    selected_audio_path = st.session_state.get("studio_selected_audio_asset_path")
    selected_asset_paths = st.session_state.get("studio_selected_asset_paths") or []

    render_studio_hero(
        "Media Studio",
        "内容优先的音视频工作台。先沉淀内容，再生成声音、视频和数字人口播，所有结果都可以回流为可复用资产。",
    )

    render_metric_cards(
        [
            ("Content Items", str(len(content_items))),
            ("Audio Assets", str(len(audio_assets))),
            ("Video Assets", str(len(video_assets))),
            ("Local Voice", "OmniVoice"),
        ]
    )

    render_workspace_context(
        [
            (
                "Selected Content",
                selected_content.get("title") if selected_content else "",
                selected_content.get("content_type") if selected_content else None,
            ),
            (
                "Selected Audio",
                Path(selected_audio_path).name if selected_audio_path and Path(selected_audio_path).exists() else "",
                "数字人口播会自动把它作为声音参考",
            ),
            (
                "Preloaded Assets",
                f"{len(selected_asset_paths)} 项" if selected_asset_paths else "",
                "来自资产库的视频素材会直接带入自定义素材",
            ),
        ],
        note="推荐路径：先在内容库沉淀内容，再进入音频工坊或视频工坊；如果你已经选中过内容或素材，这里会持续保留当前上下文。",
    )

    st.markdown("### 继续工作")
    resume_cols = st.columns(3, gap="large")
    with resume_cols[0]:
        with st.container(border=True):
            st.markdown("**从内容开始**")
            st.caption("导入 PDF、格言、路线或脚本，建立后续所有工作流的内容基底。")
            st.page_link("pages/2_📚_Content_Library.py", label="打开内容库", width="stretch")
    with resume_cols[1]:
        with st.container(border=True):
            st.markdown("**先做声音**")
            st.caption("把选中的内容做成旁白，沉淀为后续视频和数字人的声音资产。")
            st.page_link("pages/3_🎙️_Audio_Workshop.py", label="打开音频工坊", width="stretch")
    with resume_cols[2]:
        with st.container(border=True):
            st.markdown("**复用已有资产**")
            st.caption("如果已经生成过视频或声音，可以直接从资产库继续接下来的工作。")
            st.page_link("pages/6_🗂️_Asset_Library.py", label="打开资产库", width="stretch")
    settings_col = st.columns(1)[0]
    with settings_col:
        with st.container(border=True):
            st.markdown("**系统设置**")
            st.caption("把大模型、ComfyUI 和发布配置统一放在一个页面维护，不再打断创作工作流。")
            st.page_link("pages/7_⚙️_Settings.py", label="打开 Settings", width="stretch")

    st.markdown("### 核心模块")
    render_module_cards(
        [
            ("内容库", "导入 PDF、书籍、路线、格言和脚本，保存为长期可复用的内容资产。", "pages/2_📚_Content_Library.py"),
            ("音频工坊", "用 OmniVoice、本地 TTS 或 ComfyUI TTS 生成旁白，并沉淀为声音素材。", "pages/3_🎙️_Audio_Workshop.py"),
            ("视频工坊", "从文档、主题、图片或素材快速生成视频，逐步收敛到内容驱动主线。", "pages/4_🎬_Video_Workshop.py"),
            ("数字人口播", "保留独立数字人生产模块，适合讲解、带货、口播和主持场景。", "pages/5_🤖_Digital_Human.py"),
            ("资产库", "集中查看最近沉淀的声音和视频资产，方便复用、预览和导出。", "pages/6_🗂️_Asset_Library.py"),
            ("Settings", "统一管理 LLM、ComfyUI、HyperFrames 和发布相关系统配置。", "pages/7_⚙️_Settings.py"),
        ]
    )

    st.markdown("### 当前方向")
    st.info(
        "V1 优先把“内容库 -> 音频工坊 -> 视频工坊/数字人口播”的链路做顺。"
        " 通用素材和高级工作流会保留，但不再作为默认产品叙事中心。"
    )

    left_col, middle_col, right_col = st.columns([1.05, 0.95, 1.0], gap="large")
    with left_col:
        st.markdown("### 最近内容")
        if not content_items:
            st.caption("还没有内容资产。先去内容库导入一本 PDF、一本书稿或一组格言。")
        else:
            for item in content_items[:5]:
                with st.container(border=True):
                    st.markdown(f"**{item.get('title') or item.get('content_id')}**")
                    meta = f"{item.get('content_type', 'content')} · {item.get('char_count', 0)} 字"
                    if item.get("source_filename"):
                        meta += f" · {item['source_filename']}"
                    st.caption(meta)
                    if item.get("summary"):
                        st.write(item["summary"])

    with middle_col:
        st.markdown("### 最近声音资产")
        if not audio_assets:
            st.caption("还没有声音素材。可以在音频工坊里先生成一批 OmniVoice 旁白。")
        else:
            for asset in audio_assets[:5]:
                with st.container(border=True):
                    st.markdown(f"**{asset.get('title') or asset.get('asset_id')}**")
                    details = [asset.get("engine") or "audio", asset.get("voice") or "default"]
                    if asset.get("duration_seconds"):
                        details.append(f"{asset['duration_seconds']:.1f}s")
                    st.caption(" · ".join(str(detail) for detail in details if detail))
                    audio_path = asset.get("audio_path")
                    if audio_path and Path(audio_path).exists():
                        st.audio(audio_path)

    with right_col:
        st.markdown("### 最近视频资产")
        if not video_assets:
            st.caption("还没有视频资产。去视频工坊生成一个成片后，这里会自动汇总。")
        else:
            for asset in video_assets[:5]:
                with st.container(border=True):
                    st.markdown(f"**{asset.get('title') or asset.get('asset_id')}**")
                    details = []
                    if asset.get("duration"):
                        details.append(f"{asset['duration']:.1f}s")
                    if asset.get("n_frames"):
                        details.append(f"{asset['n_frames']} 镜头")
                    if asset.get("pipeline"):
                        details.append(str(asset["pipeline"]))
                    st.caption(" · ".join(details))
                    if asset.get("source_text_preview"):
                        st.write(asset["source_text_preview"])


if __name__ == "__main__":
    main()
