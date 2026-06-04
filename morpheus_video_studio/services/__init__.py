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

Services:
- LLMService: LLM text generation
- TTSService: Text-to-speech
- MediaService: Media generation (image & video)
- VideoService: Video processing
- FrameProcessor: Frame processing orchestrator
- PersistenceService: Task metadata and storyboard persistence
- HistoryManager: History management business logic
- ComfyBaseService: Base class for ComfyUI-based services
"""

from morpheus_video_studio.services.comfy_base_service import ComfyBaseService
from morpheus_video_studio.services.llm_service import LLMService
from morpheus_video_studio.services.tts_service import TTSService
from morpheus_video_studio.services.media import MediaService
from morpheus_video_studio.services.video import VideoService
from morpheus_video_studio.services.frame_processor import FrameProcessor
from morpheus_video_studio.services.persistence import PersistenceService
from morpheus_video_studio.services.history_manager import HistoryManager

# Backward compatibility alias
ImageService = MediaService

__all__ = [
    "ComfyBaseService",
    "LLMService",
    "TTSService",
    "MediaService",
    "ImageService",  # Backward compatibility
    "VideoService",
    "FrameProcessor",
    "PersistenceService",
    "HistoryManager",
]

