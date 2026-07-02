from __future__ import annotations

import json
from typing import Any

import streamlit as st

from morpheus_video_studio.utils.content_generators import generate_seedance_script
from web.pipelines.base import PipelineUI, register_pipeline_ui
from web.utils.async_helpers import run_async


class SeedanceScriptPipelineUI(PipelineUI):
    name = "seedance_script"
    display_name = "Seedance 脚本"
    icon = "🎥"
    description = "基于 Seedance 2.0 规范生成可直接粘贴到即梦的视频脚本和分镜提示词。"

    def render(self, morpheus_video_studio: Any):
        left, right = st.columns([0.9, 1.1], gap="large")

        with left:
            with st.container(border=True):
                st.markdown("**脚本设定**")
                brief = st.text_area(
                    "创意简述",
                    height=180,
                    placeholder="例如：为一款冷萃咖啡生成 10 秒竖屏广告，风格清爽高级，突出早晨提神。",
                    key="seedance_brief",
                )
                duration_seconds = st.slider(
                    "生成时长",
                    min_value=4,
                    max_value=15,
                    value=10,
                    step=1,
                    key="seedance_duration",
                )
                scenario = st.selectbox(
                    "场景类型",
                    ["general", "ecommerce_ad", "short_drama", "education", "music_video", "video_extension", "video_edit"],
                    format_func=lambda value: {
                        "general": "通用",
                        "ecommerce_ad": "电商广告",
                        "short_drama": "短剧",
                        "education": "科普教育",
                        "music_video": "音乐卡点",
                        "video_extension": "视频延长",
                        "video_edit": "视频编辑",
                    }.get(value, value),
                    key="seedance_scenario",
                )
                aspect_ratio = st.selectbox(
                    "画幅",
                    ["9:16", "16:9", "1:1"],
                    key="seedance_aspect_ratio",
                )
                language = st.selectbox(
                    "输出语言",
                    ["auto", "zh", "en"],
                    format_func=lambda value: {"auto": "自动判断", "zh": "中文", "en": "English"}.get(value, value),
                    key="seedance_language",
                )

            with st.container(border=True):
                st.markdown("**素材引用**")
                st.caption("每行一个素材：类型 | 名称或路径 | 角色。类型可填 image / video / audio。")
                assets_raw = st.text_area(
                    "素材列表",
                    height=150,
                    placeholder="image | 产品主图 | 产品外观\nvideo | 运镜参考.mp4 | 运镜和节奏\naudio | bgm.mp3 | 背景音乐",
                    key="seedance_assets_raw",
                )
                generate_clicked = st.button("生成 Seedance 脚本", type="primary", width="stretch")

        with right:
            with st.container(border=True):
                st.markdown("**生成结果**")
                if generate_clicked:
                    if not brief.strip():
                        st.error("先填写创意简述。")
                    elif morpheus_video_studio.llm is None:
                        st.error("LLM 服务还没有初始化。")
                    else:
                        assets = _parse_assets(assets_raw)
                        with st.spinner("正在生成 Seedance 脚本..."):
                            script = run_async(
                                generate_seedance_script(
                                    llm_service=morpheus_video_studio.llm,
                                    brief=brief,
                                    duration_seconds=duration_seconds,
                                    assets=assets,
                                    language=language,
                                    scenario=scenario,
                                    aspect_ratio=aspect_ratio,
                                )
                            )
                        st.session_state["seedance_script_result"] = script

                script = st.session_state.get("seedance_script_result")
                if not script:
                    st.info("结果会显示在这里，包括可直接复制的 Seedance 提示词、分镜和素材使用计划。")
                    return

                if script.get("summary"):
                    st.write(script["summary"])

                st.text_area(
                    "Seedance 提示词",
                    value=script.get("seedance_prompt", ""),
                    height=260,
                    key="seedance_prompt_output",
                )

                scenes = script.get("scenes") or []
                if scenes:
                    st.markdown("**分镜**")
                    for index, scene in enumerate(scenes, start=1):
                        with st.expander(f"{index}. {scene.get('time_range', '')}", expanded=index == 1):
                            st.write(scene.get("visual", ""))
                            if scene.get("camera"):
                                st.caption(f"运镜：{scene['camera']}")
                            if scene.get("motion"):
                                st.caption(f"动作：{scene['motion']}")
                            if scene.get("audio"):
                                st.caption(f"声音：{scene['audio']}")

                st.download_button(
                    "下载 JSON",
                    data=json.dumps(script, ensure_ascii=False, indent=2),
                    file_name="seedance_script.json",
                    mime="application/json",
                    width="stretch",
                )


def _parse_assets(raw: str) -> list[dict[str, str]]:
    assets = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) == 1:
            assets.append({"type": "image", "label": parts[0], "role": "reference material"})
        elif len(parts) == 2:
            assets.append({"type": parts[0] or "image", "label": parts[1], "role": "reference material"})
        else:
            assets.append({"type": parts[0] or "image", "label": parts[1], "role": parts[2]})
    return assets[:12]


register_pipeline_ui(SeedanceScriptPipelineUI)
