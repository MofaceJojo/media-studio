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
Morpheus Video Studio Services

Core services providing atomic capabilities.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from morpheus_video_studio.services.comfy_base_service import ComfyBaseService
    from morpheus_video_studio.services.frame_processor import FrameProcessor
    from morpheus_video_studio.services.history_manager import HistoryManager
    from morpheus_video_studio.services.llm_service import LLMService
    from morpheus_video_studio.services.media import MediaService
    from morpheus_video_studio.services.persistence import PersistenceService
    from morpheus_video_studio.services.tts_service import TTSService
    from morpheus_video_studio.services.video import VideoService


__all__ = [
    "ComfyBaseService",
    "LLMService",
    "TTSService",
    "MediaService",
    "ImageService",
    "VideoService",
    "FrameProcessor",
    "PersistenceService",
    "HistoryManager",
]


def __getattr__(name: str):
    if name == "ComfyBaseService":
        from morpheus_video_studio.services.comfy_base_service import ComfyBaseService

        return ComfyBaseService
    if name == "LLMService":
        from morpheus_video_studio.services.llm_service import LLMService

        return LLMService
    if name == "TTSService":
        from morpheus_video_studio.services.tts_service import TTSService

        return TTSService
    if name in {"MediaService", "ImageService"}:
        from morpheus_video_studio.services.media import MediaService

        return MediaService
    if name == "VideoService":
        from morpheus_video_studio.services.video import VideoService

        return VideoService
    if name == "FrameProcessor":
        from morpheus_video_studio.services.frame_processor import FrameProcessor

        return FrameProcessor
    if name == "PersistenceService":
        from morpheus_video_studio.services.persistence import PersistenceService

        return PersistenceService
    if name == "HistoryManager":
        from morpheus_video_studio.services.history_manager import HistoryManager

        return HistoryManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
