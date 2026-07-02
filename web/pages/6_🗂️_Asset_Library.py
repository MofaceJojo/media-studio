import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from morpheus_video_studio.services.studio_library import StudioLibraryService
from web.components.faq import render_faq_sidebar
from web.components.studio_shell import inject_studio_css, render_metric_cards, render_studio_hero, render_workspace_context
from web.state.session import init_i18n, init_session_state


def _format_file_size(num_bytes: int | None) -> str | None:
    if not num_bytes:
        return None
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    if num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / 1024 / 1024:.1f} MB"
    return f"{num_bytes / 1024 / 1024 / 1024:.2f} GB"


def main():
    init_session_state()
    init_i18n()
    inject_studio_css()
    render_faq_sidebar()
    render_studio_hero(
        "资产库",
        "集中查看已经沉淀下来的声音和视频资产。这里不是生成入口，而是复用和回看的资产工作台。",
        kicker="Asset Library",
    )

    library = StudioLibraryService()
    audio_assets = library.list_audio_assets()
    video_assets = library.list_video_assets()
    selected_audio_path = st.session_state.get("studio_selected_audio_asset_path")
    selected_asset_paths = st.session_state.get("studio_selected_asset_paths") or []

    render_metric_cards(
        [
            ("Audio Assets", str(len(audio_assets))),
            ("Video Assets", str(len(video_assets))),
            (
                "Latest Video",
                video_assets[0].get("title", "None")[:18] if video_assets else "None",
            ),
        ]
    )

    render_workspace_context(
        [
            (
                "Selected Audio",
                Path(selected_audio_path).name if selected_audio_path and Path(selected_audio_path).exists() else "",
                "用于数字人口播的声音参考",
            ),
            (
                "Preloaded Assets",
                f"{len(selected_asset_paths)} 项" if selected_asset_paths else "",
                "会带回视频工坊的自定义素材工作区",
            ),
        ],
        note="资产库只负责复用、预览和导出，不承担新生成逻辑。把这里当成你的成品与中间素材工作台。",
    )

    audio_tab, video_tab = st.tabs(["🎙️ 声音资产", "🎬 视频资产"])

    with audio_tab:
        st.markdown("### 最近声音资产")
        if not audio_assets:
            st.caption("还没有声音资产。先去音频工坊生成一条旁白。")
        for asset in audio_assets:
            with st.container(border=True):
                st.markdown(f"**{asset.get('title') or asset.get('asset_id')}**")
                details = [
                    asset.get("engine"),
                    asset.get("voice"),
                    f"{asset['duration_seconds']:.1f}s" if asset.get("duration_seconds") else None,
                ]
                st.caption(" · ".join(detail for detail in details if detail))
                if asset.get("source_text_preview"):
                    st.write(asset["source_text_preview"])
                audio_path = asset.get("audio_path")
                if audio_path and Path(audio_path).exists():
                    st.audio(audio_path)
                    if st.button("用于数字人口播", key=f"use_audio_for_digital_{asset['asset_id']}", width="stretch"):
                        st.session_state["studio_selected_audio_asset_path"] = audio_path
                        st.session_state["digital_tts_inference_mode"] = "comfyui"
                        if asset.get("content_id"):
                            st.session_state["studio_selected_content_id"] = asset["content_id"]
                        st.switch_page("pages/5_🤖_Digital_Human.py")

    with video_tab:
        st.markdown("### 最近视频资产")
        if not video_assets:
            st.caption("还没有视频资产。先去视频工坊生成一个成片。")
        for asset in video_assets:
            with st.container(border=True):
                st.markdown(f"**{asset.get('title') or asset.get('asset_id')}**")
                details = [
                    asset.get("pipeline"),
                    f"{asset['duration']:.1f}s" if asset.get("duration") else None,
                    f"{asset['n_frames']} 镜头" if asset.get("n_frames") else None,
                    _format_file_size(asset.get("file_size")),
                ]
                st.caption(" · ".join(detail for detail in details if detail))
                if asset.get("source_text_preview"):
                    st.write(asset["source_text_preview"])
                video_path = asset.get("video_path")
                if video_path and Path(video_path).exists():
                    st.video(video_path)
                    if st.button("用于自定义素材", key=f"use_video_for_custom_{asset['asset_id']}", width="stretch"):
                        st.session_state["studio_selected_asset_paths"] = [video_path]
                        st.session_state["studio_video_workshop_section"] = "custom_media"
                        st.switch_page("pages/4_🎬_Video_Workshop.py")
                    with open(video_path, "rb") as video_file:
                        st.download_button(
                            "下载视频",
                            data=video_file.read(),
                            file_name=Path(video_path).name,
                            mime="video/mp4",
                            key=f"asset_video_download_{asset['asset_id']}",
                            width="stretch",
                        )


if __name__ == "__main__":
    main()
