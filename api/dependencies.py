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
FastAPI Dependencies

Provides dependency injection for MorpheusVideoStudioCore and other services.
"""

from typing import Annotated
from fastapi import Depends
from loguru import logger

from morpheus_video_studio.service import MorpheusVideoStudioCore


# Global Morpheus Video Studio instance
_morpheus_video_studio_instance: MorpheusVideoStudioCore = None


async def get_morpheus_video_studio() -> MorpheusVideoStudioCore:
    """
    Get Morpheus Video Studio core instance (dependency injection)
    
    Returns:
        MorpheusVideoStudioCore instance
    """
    global _morpheus_video_studio_instance
    
    if _morpheus_video_studio_instance is None:
        _morpheus_video_studio_instance = MorpheusVideoStudioCore()
        await _morpheus_video_studio_instance.initialize()
        logger.info("✅ Morpheus Video Studio initialized for API")
    
    return _morpheus_video_studio_instance


async def shutdown_morpheus_video_studio():
    """Shutdown Morpheus Video Studio instance and cleanup resources"""
    global _morpheus_video_studio_instance
    if _morpheus_video_studio_instance:
        logger.info("Shutting down Morpheus Video Studio...")
        await _morpheus_video_studio_instance.cleanup()
        _morpheus_video_studio_instance = None
    
    from morpheus_video_studio.services.frame_html import HTMLFrameGenerator
    await HTMLFrameGenerator.close_browser()


# Type alias for dependency injection
MorpheusVideoStudioDep = Annotated[MorpheusVideoStudioCore, Depends(get_morpheus_video_studio)]

