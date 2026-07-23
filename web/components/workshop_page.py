"""Helpers for rendering curated pipeline workshop pages."""

from __future__ import annotations

import streamlit as st

from web.components.faq import render_faq_sidebar
from web.components.settings import render_advanced_settings
from web.components.studio_shell import inject_studio_css, render_studio_hero
from web.state.session import get_morpheus_video_studio, init_i18n, init_session_state


def render_pipeline_workshop(
    title: str,
    subtitle: str,
    pipeline_names: list[str],
) -> None:
    init_session_state()
    init_i18n()
    inject_studio_css()
    render_faq_sidebar()
    render_studio_hero(title, subtitle)

    morpheus_video_studio = get_morpheus_video_studio()
    render_advanced_settings()

    from web.pipelines import get_pipeline_ui

    pipelines = [get_pipeline_ui(name) for name in pipeline_names]
    pipelines = [pipeline for pipeline in pipelines if pipeline is not None]
    if not pipelines:
        st.error("没有找到可用的工作流入口。")
        return

    tab_labels = [f"{pipeline.icon} {pipeline.display_name}" for pipeline in pipelines]
    tabs = st.tabs(tab_labels)
    for tab, pipeline in zip(tabs, pipelines):
        with tab:
            if pipeline.description:
                st.caption(pipeline.description)
            pipeline.render(morpheus_video_studio)
