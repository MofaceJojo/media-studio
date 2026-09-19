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
Workflow Path Resolver

Standardized workflow path resolution for all ComfyUI services.
Convention: {source}/{service}.json

Examples:
    - Image analysis: selfhost/analyse_image.json, selfhost/analyse_image.json
    - Image generation: selfhost/image.json, selfhost/image.json
    - Video generation: selfhost/video.json, selfhost/video.json
    - TTS: selfhost/tts.json, selfhost/tts.json
"""

from typing import Literal

WorkflowSource = Literal['selfhost']


def resolve_workflow_path(
    service_name: str,
    source: WorkflowSource = 'selfhost'
) -> str:
    """
    Resolve workflow path using standardized naming convention
    
    Convention: workflows/{source}/{service_name}.json
    
    Args:
        service_name: Service identifier (e.g., "analyse_image", "image", "video", "tts")
        source: Workflow source - 'selfhost' (default) or 'selfhost'
    
    Returns:
        Workflow path in format: "{source}/{service_name}.json"
        
    Examples:
        >>> resolve_workflow_path("analyse_image", "selfhost")
        'selfhost/analyse_image.json'
        
        >>> resolve_workflow_path("analyse_image", "selfhost")
        'selfhost/analyse_image.json'
        
        >>> resolve_workflow_path("image")  # defaults to selfhost
        'selfhost/image.json'
    """
    return f"{source}/{service_name}.json"


def get_default_source() -> WorkflowSource:
    """
    Get default workflow source
    
    Returns:
        'selfhost' - Cloud-first approach, better for beginners
    """
    return 'selfhost'
