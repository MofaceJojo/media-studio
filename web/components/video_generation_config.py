"""Video and subtitle settings for quick creation."""

from pathlib import Path
import random

import streamlit as st

from morpheus_video_studio.services.frame_html import HTMLFrameGenerator
from morpheus_video_studio.utils.template_util import get_template_full_path, list_templates_for_size

VIDEO_SOURCES = {
    "auto": "跟随上方媒体生成策略（推荐）",
    "all": "全部（Pexels + Pixabay）",
    "pexels": "Pexels",
    "pixabay": "Pixabay",
}

TRANSITION_OPTIONS = {
    "none": "无转场",
    "fade": "淡入淡出",
    "dissolve": "溶解",
    "fadeblack": "淡黑",
    "fadewhite": "淡白",
    "wipeleft": "向左擦除",
    "wiperight": "向右擦除",
    "slideleft": "左滑推进",
    "slideright": "右滑推进",
    "circleopen": "圆形展开",
    "circleclose": "圆形闭合",
    "zoomin": "镜头推进",
    "coverdown": "上覆盖下",
    "revealup": "向上揭开",
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

IMAGE_MOTION_OPTIONS = {
    "none": "无特效",
    "gentle": "轻微飘移",
    "float": "缓慢飘逸缩放",
    "cinematic": "电影感推拉",
}

DEFAULT_IMAGE_MOTIONS = ["gentle", "float"]

DEFAULT_TRANSITIONS = ["fade", "dissolve", "fadeblack"]


def _estimate_scene_trailing_silence(transition_duration: float) -> float:
    """Default to strict audio-driven timing without extra post-line silence."""
    return 0.0


def _pick_random_subset(options: list[str]) -> list[str]:
    """Return a non-empty random subset for quick one-click style changes."""
    if not options:
        return []
    sample_size = random.randint(1, len(options))
    return random.sample(options, sample_size)


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


def _estimate_video_duration_seconds(
    n_scenes: int,
    clip_duration: float,
    min_segment_duration: float,
    tts_speed: float,
    transition_mode: str,
    transition_choices: list[str],
    transition_duration: float,
) -> float:
    """Estimate final duration from current pacing and overlap settings."""
    effective_tts_speed = max(float(tts_speed or 1.0), 0.5)
    estimated_audio_per_scene = (
        float(clip_duration) / effective_tts_speed
        + _estimate_scene_trailing_silence(transition_duration)
    )
    estimated_scene_duration = max(float(min_segment_duration), estimated_audio_per_scene)
    total_duration = max(int(n_scenes), 0) * estimated_scene_duration

    active_transitions = 0
    if transition_mode != "none" and [item for item in transition_choices if item != "none"]:
        active_transitions = max(int(n_scenes) - 1, 0)
    total_duration -= active_transitions * float(transition_duration)
    return max(total_duration, 0.0)


def render_video_generation_config(
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
            if st.button("一键随机切换转场与特效", key="quick_video_randomize_fx"):
                st.session_state["quick_video_transition_choices"] = _pick_random_subset(
                    [name for name in TRANSITION_OPTIONS if name != "none"]
                )
                st.session_state["quick_video_transition_random"] = True
                st.session_state["quick_video_image_motion_choices"] = _pick_random_subset(
                    [name for name in IMAGE_MOTION_OPTIONS if name != "none"]
                )
                st.session_state["quick_video_image_motion_random"] = True
                st.rerun()
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
                transition_choices = st.multiselect(
                    "片段转场",
                    list(TRANSITION_OPTIONS),
                    default=DEFAULT_TRANSITIONS,
                    format_func=lambda value: TRANSITION_OPTIONS[value],
                    help="可多选几种转场；下面可以选择随机使用或按顺序轮换。",
                    key="quick_video_transition_choices",
                )
                transition_random = st.checkbox(
                    "随机使用已选转场",
                    value=True,
                    key="quick_video_transition_random",
                )
            with output_col:
                transition_duration = st.slider(
                    "转场时长(秒)",
                    min_value=0.3,
                    max_value=1.5,
                    value=0.5,
                    step=0.1,
                    key="quick_video_transition_duration",
                )
                min_segment_duration = st.slider(
                    "额外最短镜头停留(秒)",
                    min_value=0.0,
                    max_value=20.0,
                    value=0.0,
                    step=0.5,
                    help="0 表示严格跟随配音时长；只有你想故意让镜头多停一会儿时才需要调大。",
                    key="quick_video_min_segment_duration",
                )
                clip_duration = st.slider(
                    "单片段最大时长(秒)",
                    min_value=2,
                    max_value=30,
                    value=8,
                    step=1,
                    help="用于控制自动生成文案时每段旁白的目标长度；默认更长，减少镜头切得太碎。最终成片仍会优先保证配音完整。",
                    key="quick_video_clip_duration",
                )
                video_count = st.selectbox(
                    "生成视频数量",
                    [1, 2, 3, 4, 5],
                    help="数量大于 1 时会进入批量生成，使用相同文案与设置生成多条素材变体。",
                    key="quick_video_count",
                )
                image_motion_choices = st.multiselect(
                    "画面特效",
                    list(IMAGE_MOTION_OPTIONS),
                    default=DEFAULT_IMAGE_MOTIONS,
                    format_func=lambda value: IMAGE_MOTION_OPTIONS[value],
                    help="可多选几种镜头运动特效；下面可以选择随机使用或按顺序轮换。",
                    key="quick_video_image_motion_choices",
                )
                image_motion_random = st.checkbox(
                    "随机使用已选画面特效",
                    value=True,
                    key="quick_video_image_motion_random",
                )

            n_scenes = int(
                st.session_state.get("quick_create_effective_n_scenes")
                or st.session_state.get("quick_create_n_scenes", 5)
                or 5
            )
            tts_speed = float(style_params.get("tts_speed") or 1.0)
            transition_mode = (
                "none" if not transition_choices
                else "random" if transition_random and len(transition_choices) > 1
                else "sequence" if len(transition_choices) > 1
                else transition_choices[0]
            )
            estimated_duration = _estimate_video_duration_seconds(
                n_scenes=n_scenes,
                clip_duration=float(clip_duration),
                min_segment_duration=float(min_segment_duration),
                tts_speed=tts_speed,
                transition_mode=transition_mode,
                transition_choices=transition_choices,
                transition_duration=float(transition_duration),
            )
            overlap_count = max(n_scenes - 1, 0) if transition_mode != "none" and transition_choices else 0
            st.info(
                "预估成片时长："
                f" 约 {estimated_duration:.1f} 秒"
                f"（{n_scenes} 段，单段约 {max(float(min_segment_duration), float(clip_duration) / max(tts_speed, 0.5)):.1f} 秒"
                + (f"，转场重叠 {overlap_count} 次 × {float(transition_duration):.1f} 秒" if overlap_count else "")
                + "）"
            )
            st.caption("这是按当前分镜数、TTS 语速、单段时长和转场重叠计算的预估值，实际会随 AI 生成旁白长短略有浮动。")

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
        "transition_choices": transition_choices,
        "transition_duration": transition_duration,
        "min_segment_duration": min_segment_duration,
        "scene_trailing_silence": _estimate_scene_trailing_silence(float(transition_duration)),
        "image_motion_mode": (
            "none" if not image_motion_choices
            else "random" if image_motion_random and len(image_motion_choices) > 1
            else "sequence" if len(image_motion_choices) > 1
            else image_motion_choices[0]
        ),
        "image_motion_choices": image_motion_choices,
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
