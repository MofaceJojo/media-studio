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
Morpheus Video Studio - AI-powered video generator

Convention-based system with unified configuration management.

Usage:
    from morpheus_video_studio import morpheus_video_studio
    
    # Initialize
    await morpheus_video_studio.initialize()
    
    # Use capabilities
    answer = await morpheus_video_studio.llm("Explain atomic habits")
    audio = await morpheus_video_studio.tts("Hello world")
    
    # Generate video with different pipelines
    # Standard pipeline (default)
    result = await morpheus_video_studio.generate_video(
        text="如何提高学习效率",
        n_scenes=5
    )
    
    # Custom pipeline (template for your own logic)
    result = await morpheus_video_studio.generate_video(
        text=your_content,
        pipeline="custom",
        custom_param_example="custom_value"
    )
    
    # Check available pipelines
    print(morpheus_video_studio.pipelines.keys())  # dict_keys(['standard', 'custom'])
"""

from typing import TYPE_CHECKING

from morpheus_video_studio.config import config_manager

if TYPE_CHECKING:
    from morpheus_video_studio.service import MorpheusVideoStudioCore, morpheus_video_studio

__version__ = "0.1.0"

__all__ = ["MorpheusVideoStudioCore", "morpheus_video_studio", "config_manager"]


def __getattr__(name: str):
    if name in {"MorpheusVideoStudioCore", "morpheus_video_studio"}:
        from morpheus_video_studio.service import (
            MorpheusVideoStudioCore,
            morpheus_video_studio,
        )

        exports = {
            "MorpheusVideoStudioCore": MorpheusVideoStudioCore,
            "morpheus_video_studio": morpheus_video_studio,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
