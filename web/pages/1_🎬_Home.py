# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Home Page - Main video generation interface
"""

import sys
from pathlib import Path

# Add project root to sys.path
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

# Import state management
from web.state.session import init_session_state, init_i18n, get_morpheus_video_studio

# Import components
from web.components.header import render_header
from web.components.settings import render_advanced_settings
from web.components.faq import render_faq_sidebar

# Page config
st.set_page_config(
    page_title="Home - Morpheus Video Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main():
    """Main UI entry point"""
    # Initialize session state and i18n
    init_session_state()
    init_i18n()
    
    # Render header (title + language selector)
    render_header()
    
    # Render FAQ in sidebar
    render_faq_sidebar()
    
    # Initialize Morpheus Video Studio
    morpheus_video_studio = get_morpheus_video_studio()
    
    # Render system configuration (LLM + ComfyUI)
    render_advanced_settings()
    
    # ========================================================================
    # Pipeline Selection & Delegation
    # ========================================================================
    from web.pipelines import get_all_pipeline_uis
    
    # Get all registered pipelines
    pipelines = get_all_pipeline_uis()
    
    # Use Tabs for pipeline selection
    # Note: st.tabs returns a list of containers, one for each tab
    tab_labels = [f"{p.icon} {p.display_name}" for p in pipelines]
    tabs = st.tabs(tab_labels)
    
    # Render each pipeline in its corresponding tab
    for i, pipeline in enumerate(pipelines):
        with tabs[i]:
            # Show description if available
            if pipeline.description:
                st.caption(pipeline.description)
            
            # Delegate rendering
            pipeline.render(morpheus_video_studio)


if __name__ == "__main__":
    main()

