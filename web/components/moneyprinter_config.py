"""MoneyPrinterTurbo-style video and subtitle settings for quick creation."""

from pathlib import Path

import streamlit as st

from morpheus_video_studio.services.frame_html import HTMLFrameGenerator
from morpheus_video_studio.utils.template_util import get_template_full_path, list_templates_for_size

VIDEO_SOURCES = {
    "auto": "跟随上方媒体生成策略（推荐）",
    "all": "全部（Pexels + Pixabay）",
    "pexels": "Pexels",
    "pixabay": "Pixabay",
}

VIDEO_RATIOS = {
    "portrait": ("竖屏 9:16（抖音视频）", "1080x1920"),
    "landscape": ("横屏 16:9（YouTube）", "1920x1080"),
    "square": ("方形 1:1", "1080x1080"),
}

SUBTITLE_FONTS = {
    "Microsoft YaHei": "MicrosoftYaHeiBold.ttc",
    "PingFang SC": "PingFang SC",
    "Source Han Sans SC": "思源黑体",
    "Arial": "Arial",
}


def _template_for_ratio(current_template: str, size: str) -> str:
    """Keep the selected template name when the requested size provides it."""
    template_name = Path(current_template).name
    available = list_templates_for_size(size)
    if not available:
        return current_template
    if template_name not in available:
        preferred = [
            name for name in available
            if name in ("video_default.html", "image_full.html", "image_default.html")
        ]
        template_name = preferred[0] if preferred else available[0]
    return get_template_full_path(size, template_name)


def render_moneyprinter_config(
    style_params: dict,
    video_container=None,
    subtitle_container=None,
) -> dict:
    """Render video/subtitle settings and return generation parameter overrides."""
    current_size = Path(style_params["frame_template"]).parent.name
    current_ratio = next(
        (key for key, (_, size) in VIDEO_RATIOS.items() if size == current_size),
        "portrait",
    )
    if video_container is None or subtitle_container is None:
        video_col, subtitle_col = st.columns(2)
        video_container = video_container or video_col
        subtitle_container = subtitle_container or subtitle_col

    with video_container:
        with st.container(border=True):
            st.markdown("**视频与素材设置**")
            source_col, edit_col, output_col = st.columns(3, gap="large")
            with source_col:
                video_source = st.selectbox(
                    "素材来源",
                    list(VIDEO_SOURCES),
                    format_func=VIDEO_SOURCES.get,
                    key="quick_video_source",
                )
                ratio = st.selectbox(
                    "成片比例",
                    list(VIDEO_RATIOS),
                    format_func=lambda value: VIDEO_RATIOS[value][0],
                    index=list(VIDEO_RATIOS).index(current_ratio),
                    key="quick_video_ratio",
                )
            with edit_col:
                concat_mode = st.selectbox(
                    "素材选择方式",
                    ["random", "sequential"],
                    format_func=lambda value: {
                        "random": "随机素材（推荐）",
                        "sequential": "顺序素材",
                    }[value],
                    key="quick_video_concat_mode",
                )
                transition_mode = st.selectbox(
                    "片段转场",
                    ["none", "fade"],
                    format_func=lambda value: {
                        "none": "无转场",
                        "fade": "淡入淡出",
                    }[value],
                    key="quick_video_transition_mode",
                )
            with output_col:
                clip_duration = st.selectbox(
                    "单片段最大时长(秒)",
                    [2, 3, 4, 5, 6, 8, 10],
                    index=1,
                    help="用于控制自动生成文案的单段长度；最终片段仍会优先保证配音完整。",
                    key="quick_video_clip_duration",
                )
                video_count = st.selectbox(
                    "生成视频数量",
                    [1, 2, 3, 4, 5],
                    help="数量大于 1 时会进入批量生成，使用相同文案与设置生成多条素材变体。",
                    key="quick_video_count",
                )

    with subtitle_container:
        with st.container(border=True):
            st.markdown("**字幕设置**")
            subtitle_enabled = st.checkbox(
                "启用字幕（若取消勾选，下面的设置都将不生效）",
                value=True,
                key="quick_subtitle_enabled",
            )
            subtitle_font = st.selectbox(
                "字幕字体",
                list(SUBTITLE_FONTS),
                format_func=SUBTITLE_FONTS.get,
                disabled=not subtitle_enabled,
                key="quick_subtitle_font",
            )
            subtitle_position = st.selectbox(
                "字幕位置",
                ["bottom", "center", "top"],
                format_func=lambda value: {
                    "bottom": "底部（推荐）",
                    "center": "中部",
                    "top": "顶部",
                }[value],
                disabled=not subtitle_enabled,
                key="quick_subtitle_position",
            )
            color_col, size_col = st.columns([0.7, 1.3])
            with color_col:
                subtitle_color = st.color_picker(
                    "字幕颜色",
                    "#FFFFFF",
                    disabled=not subtitle_enabled,
                    key="quick_subtitle_color",
                )
            with size_col:
                subtitle_size = st.slider(
                    "字幕大小",
                    30,
                    100,
                    60,
                    disabled=not subtitle_enabled,
                    key="quick_subtitle_size",
                )
            stroke_col, width_col = st.columns([0.7, 1.3])
            with stroke_col:
                subtitle_stroke_color = st.color_picker(
                    "描边颜色",
                    "#000000",
                    disabled=not subtitle_enabled,
                    key="quick_subtitle_stroke_color",
                )
            with width_col:
                subtitle_stroke_width = st.slider(
                    "描边粗细",
                    0.0,
                    10.0,
                    1.5,
                    0.5,
                    disabled=not subtitle_enabled,
                    key="quick_subtitle_stroke_width",
                )

    requested_size = VIDEO_RATIOS[ratio][1]
    frame_template = _template_for_ratio(style_params["frame_template"], requested_size)
    generator = HTMLFrameGenerator(frame_template)
    media_width, media_height = generator.get_media_size()

    params = {
        "frame_template": frame_template,
        "media_width": media_width,
        "media_height": media_height,
        "stock_selection_mode": concat_mode,
        "transition_mode": transition_mode,
        "transition_duration": 0.5,
        "video_count": video_count,
        "max_narration_words": max(5, clip_duration * 4),
        "subtitle_customization_enabled": True,
        "subtitle_enabled": subtitle_enabled,
        "subtitle_font": subtitle_font,
        "subtitle_position": subtitle_position,
        "subtitle_color": subtitle_color,
        "subtitle_size": subtitle_size,
        "subtitle_stroke_color": subtitle_stroke_color,
        "subtitle_stroke_width": subtitle_stroke_width,
    }
    if video_source != "auto":
        params["media_workflow"] = f"stock/{video_source}"
        params["media_strategy"] = "stock_turbo"
    return params
