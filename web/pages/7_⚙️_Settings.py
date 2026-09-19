import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from web.components.faq import render_faq_sidebar
from web.components.settings import render_advanced_settings
from web.components.studio_shell import inject_studio_css, render_studio_hero, render_workspace_context
from web.state.session import init_i18n, init_session_state


def main():
    init_session_state()
    init_i18n()
    inject_studio_css()
    render_faq_sidebar()
    render_studio_hero(
        "Settings",
        "把大模型、ComfyUI、HyperFrames 和发布配置统一放在一个页面里管理。工作流页面只负责创作，不再混入系统级配置。",
        kicker="System Settings",
    )

    render_workspace_context(
        [
            ("What Lives Here", "LLM / ComfyUI / HyperFrames", "所有系统级配置统一维护"),
            ("Why Separate", "创作页更干净", "避免音频、视频和数字人口播页面被配置面板打断"),
        ],
        note="推荐先在这里完成基础配置，再回到内容库、音频工坊或视频工坊继续创作。",
    )

    render_advanced_settings()


if __name__ == "__main__":
    main()
