from __future__ import annotations

from typing import Any

import streamlit as st

from morpheus_video_studio.services.moneyprinter_tools import (
    create_publish_queue,
    format_platform,
    get_platform_options,
    get_publish_platforms,
)
from web.pipelines.base import PipelineUI, register_pipeline_ui


class PublishPipelineUI(PipelineUI):
    name = "auto_publish"
    display_name = "全平台发布"
    icon = "🚀"
    description = "MoneyPrinterPlus 风格的短视频发布队列，支持国内外平台并预留发布适配器。"

    def render(self, morpheus_video_studio: Any):
        platform_registry = get_publish_platforms()
        platform_options = get_platform_options()
        default_platforms = ["douyin", "kuaishou", "xiaohongshu", "shipinhao", "bilibili", "youtube", "x"]

        left, right = st.columns([0.9, 1.1])
        with left:
            with st.container(border=True):
                st.markdown("**发布内容**")
                content_dir = st.text_input("视频内容目录", value="output/moneyprinter_plus", key="publish_content_dir")
                platforms = st.multiselect(
                    "发布平台",
                    platform_options,
                    default=[platform for platform in default_platforms if platform in platform_options],
                    format_func=format_platform,
                    key="publish_platforms",
                )
                title_prefix = st.text_input("标题前缀", key="publish_title_prefix")
                tags = st.text_input("标签", placeholder="AI视频 短视频 创作", key="publish_tags")
                auto_open = st.checkbox("生成队列后打开平台上传页", value=False, key="publish_auto_open")

                if st.button("生成发布队列", type="primary", use_container_width=True):
                    try:
                        queue = create_publish_queue(content_dir, platforms, title_prefix, tags, auto_open)
                        st.session_state["publish_queue_path"] = str(queue)
                    except Exception as exc:
                        st.error(str(exc))

        with right:
            with st.container(border=True):
                st.markdown("**平台入口**")
                for platform_id, platform in platform_registry.items():
                    st.link_button(format_platform(platform_id), platform["upload_url"], use_container_width=True)
                    st.caption(f"{platform['adapter']} · API {'已接入' if platform['api_ready'] else '预留'}")
                queue_path = st.session_state.get("publish_queue_path")
                if queue_path:
                    st.success(f"发布队列已生成：{queue_path}")
                    st.caption("当前版本先生成发布清单并打开平台上传入口；自动登录和自动点击发布需在浏览器账号已登录后继续接 Selenium 执行器。")


register_pipeline_ui(PublishPipelineUI)
