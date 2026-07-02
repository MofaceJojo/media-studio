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
Morpheus Video Studio Web UI - Main Entry Point

This is the entry point for the Streamlit multi-page application.
Uses st.navigation to define pages and set the default page to Home.
"""

import sys
from pathlib import Path

# Add project root to sys.path for module imports
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

# Setup page config (must be first Streamlit command)
st.set_page_config(
    page_title="Media Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main():
    """Main entry point with navigation"""
    # Define pages using st.Page
    studio_page = st.Page(
        "pages/1_🏠_Studio.py",
        title="Studio",
        icon="🏠",
        default=True
    )

    content_page = st.Page(
        "pages/2_📚_Content_Library.py",
        title="Content Library",
        icon="📚",
    )

    audio_page = st.Page(
        "pages/3_🎙️_Audio_Workshop.py",
        title="Audio Workshop",
        icon="🎙️",
    )

    video_page = st.Page(
        "pages/4_🎬_Video_Workshop.py",
        title="Video Workshop",
        icon="🎬",
    )

    digital_human_page = st.Page(
        "pages/5_🤖_Digital_Human.py",
        title="Digital Human",
        icon="🤖",
    )

    asset_library_page = st.Page(
        "pages/6_🗂️_Asset_Library.py",
        title="Asset Library",
        icon="🗂️",
    )

    settings_page = st.Page(
        "pages/7_⚙️_Settings.py",
        title="Settings",
        icon="⚙️",
    )

    history_page = st.Page(
        "pages/2_📚_History.py",
        title="History",
        icon="🕘",
    )

    # Set up navigation and run
    pg = st.navigation(
        [studio_page, content_page, audio_page, video_page, digital_human_page, asset_library_page, settings_page, history_page]
    )
    pg.run()


if __name__ == "__main__":
    main()
