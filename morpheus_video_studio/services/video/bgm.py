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

"""Background music mixing and BGM library resolution."""

import hashlib
import os
import random
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List, Literal, Optional

import ffmpeg
from loguru import logger

from morpheus_video_studio.utils.os_util import (
    get_resource_path,
    list_resource_files,
    resource_exists
)


class BgmMixin:
    """Adds looped/once BGM under narration at a safe volume."""

    def add_bgm(
        self,
        video: str,
        bgm: str,
        output: str,
        bgm_volume: float = 0.3,
        loop: bool = True,
        fade_in: float = 0.0,
        fade_out: float = 0.0,
    ) -> str:
        """
        Add background music to video
        
        Args:
            video: Video file path
            bgm: Background music file path
            output: Output video file path
            bgm_volume: BGM volume relative to original (0.0 to 1.0+)
            loop: If True, loop BGM to match video duration
            fade_in: BGM fade-in duration in seconds
            fade_out: BGM fade-out duration in seconds (not yet implemented)
        
        Returns:
            Path to the output video file
        
        Raises:
            RuntimeError: If FFmpeg execution fails
        
        Note:
            - BGM is mixed with original video audio
            - If loop=True, BGM repeats until video ends
            - Fade effects are applied to BGM only
        """
        self._ensure_ffmpeg()
        logger.info(f"Adding BGM to video (volume={bgm_volume}, loop={loop})")
        
        try:
            input_video = ffmpeg.input(video)
            
            # Configure BGM input with looping if needed
            bgm_input = ffmpeg.input(
                bgm,
                stream_loop=-1 if loop else 0  # -1 = infinite loop
            )
            
            # Apply volume adjustment to BGM
            bgm_audio = bgm_input.audio.filter('volume', bgm_volume)
            
            # Apply fade effects if specified
            if fade_in > 0:
                bgm_audio = bgm_audio.filter('afade', type='in', duration=fade_in)
            # Note: fade_out at the end requires knowing the duration, which is complex
            # For now, we skip fade_out in this implementation
            # A more advanced implementation would need to:
            # 1. Get video duration
            # 2. Calculate fade_out start time
            # 3. Apply fade filter with specific start_time
            
            # Mix original audio with BGM
            mixed_audio = ffmpeg.filter(
                [input_video.audio, bgm_audio],
                'amix',
                inputs=2,
                duration='first'  # Use video's duration
            )
            
            (
                ffmpeg
                .output(
                    input_video.video,
                    mixed_audio,
                    output,
                    vcodec='copy',
                    acodec='aac',
                    audio_bitrate='192k'
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            logger.success(f"BGM added successfully: {output}")
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg BGM error: {error_msg}")
            raise RuntimeError(f"Failed to add BGM: {error_msg}")
    
    def _add_bgm_to_video(
        self,
        video: str,
        bgm_path: str,
        output: str,
        volume: float = 0.2,
        mode: Literal["once", "loop"] = "loop"
    ) -> str:
        """
        Internal helper to add BGM to video with path resolution
        
        Args:
            video: Video file path
            bgm_path: BGM path (can be preset name or custom path)
            output: Output file path
            volume: BGM volume (0.0-1.0)
            mode: "once" or "loop"
        
        Returns:
            Path to output video
        
        Raises:
            FileNotFoundError: If BGM file not found
        """
        # Resolve BGM path (raises FileNotFoundError if not found)
        resolved_bgm = self._resolve_bgm_path(bgm_path)
        
        # Add BGM using existing method
        loop = (mode == "loop")
        return self.add_bgm(
            video=video,
            bgm=resolved_bgm,
            output=output,
            bgm_volume=volume,
            loop=loop,
            fade_in=0.0
        )
    

    def _resolve_bgm_path(self, bgm_path: str) -> str:
        """
        Resolve BGM path (filename or custom path) with custom override support
        
        Search priority:
            1. Direct path (absolute or relative)
            2. data/bgm/{filename} (custom)
            3. bgm/{filename} (default)
        
        Args:
            bgm_path: Can be:
                - Filename with extension (e.g., "default.mp3", "happy.mp3"): auto-resolved from bgm/ or data/bgm/
                - Custom file path (absolute or relative)
        
        Returns:
            Resolved absolute path
        
        Raises:
            FileNotFoundError: If BGM file not found
        """
        # Try direct path first (absolute or relative)
        if os.path.exists(bgm_path):
            return os.path.abspath(bgm_path)
        
        # Try as filename in resource directories (custom > default)
        if resource_exists("bgm", bgm_path):
            return get_resource_path("bgm", bgm_path)
        
        # Not found - provide helpful error message
        tried_paths = [
            os.path.abspath(bgm_path),
            f"data/bgm/{bgm_path} or bgm/{bgm_path}"
        ]
        
        # List available BGM files
        available_bgm = self._list_available_bgm()
        available_msg = f"\n  Available BGM files: {', '.join(available_bgm)}" if available_bgm else ""
        
        raise FileNotFoundError(
            f"BGM file not found: '{bgm_path}'\n"
            f"  Tried paths:\n"
            f"    1. {tried_paths[0]}\n"
            f"    2. {tried_paths[1]}"
            f"{available_msg}"
        )
    
    def _list_available_bgm(self) -> list[str]:
        """
        List available BGM files (merged from bgm/ and data/bgm/)
        
        Returns:
            List of filenames (with extensions), sorted
        """
        try:
            # Use resource API to get merged list
            all_files = list_resource_files("bgm")
            
            # Filter to audio files only
            audio_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
            return sorted([f for f in all_files if f.lower().endswith(audio_extensions)])
        except Exception as e:
            logger.warning(f"Failed to list BGM files: {e}")
            return []
    
