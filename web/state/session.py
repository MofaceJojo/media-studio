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
Session state management for web UI
"""

import streamlit as st
from loguru import logger

from web.i18n import get_language, set_language
from web.utils.async_helpers import run_async


def init_session_state():
    """Initialize session state variables"""
    if "language" not in st.session_state:
        # Use auto-detected system language
        st.session_state.language = get_language()


def init_i18n():
    """Initialize internationalization"""
    # Locales are already loaded and system language detected on import
    # Get language from session state or use auto-detected system language
    if "language" not in st.session_state:
        st.session_state.language = get_language()  # Use auto-detected language
    
    # Set current language
    set_language(st.session_state.language)


def get_morpheus_video_studio():
    """
    Get initialized Morpheus Video Studio instance with proper caching and cleanup
    
    Uses st.session_state to cache the instance per user session.
    ComfyKit is lazily initialized and automatically recreated on config changes.
    """
    from morpheus_video_studio.service import MorpheusVideoStudioCore
    from morpheus_video_studio.config import config_manager
    
    # Compute config hash for change detection
    import hashlib
    import json
    config_dict = config_manager.config.to_dict()
    # Only track ComfyUI config for hash (other config changes don't need core recreation)
    comfyui_config = config_dict.get("comfyui", {})
    config_hash = hashlib.md5(json.dumps(comfyui_config, sort_keys=True).encode()).hexdigest()
    
    # Check if we need to create or recreate core instance
    need_recreate = False
    if 'morpheus_video_studio' not in st.session_state:
        need_recreate = True
        logger.info("Creating new MorpheusVideoStudioCore instance (first time)")
    elif st.session_state.get('morpheus_video_studio_config_hash') != config_hash:
        need_recreate = True
        logger.info("Configuration changed, recreating MorpheusVideoStudioCore instance")
        # Cleanup old instance
        old_core = st.session_state.morpheus_video_studio
        try:
            run_async(old_core.cleanup())
        except Exception as e:
            logger.warning(f"Failed to cleanup old MorpheusVideoStudioCore: {e}")
    
    if need_recreate:
        # Create and initialize new instance
        morpheus_video_studio = MorpheusVideoStudioCore()
        run_async(morpheus_video_studio.initialize())
        
        # Cache in session state
        st.session_state.morpheus_video_studio = morpheus_video_studio
        st.session_state.morpheus_video_studio_config_hash = config_hash
        logger.info("✅ MorpheusVideoStudioCore initialized and cached")
    else:
        morpheus_video_studio = st.session_state.morpheus_video_studio
        logger.debug("Reusing cached MorpheusVideoStudioCore instance")
    
    return morpheus_video_studio

