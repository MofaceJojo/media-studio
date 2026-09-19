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

"""Media probing and shared low-level helpers (ffprobe wrappers, temp paths)."""

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


def check_ffmpeg() -> None:
    """
    Check if FFmpeg is installed on the system
    
    Raises:
        RuntimeError: If FFmpeg is not found
    """
    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg not found. Please install it:\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu/Debian: apt-get install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )



class MediaProbeMixin:
    """ffprobe-backed inspection helpers shared by all video mixins."""

    def _get_video_fps(self, video: str) -> float:
        """Get video FPS from probe data, falling back to 30."""
        try:
            probe = ffmpeg.probe(video)
            video_info = next(s for s in probe["streams"] if s["codec_type"] == "video")
            fps_str = video_info.get("avg_frame_rate") or video_info.get("r_frame_rate") or "30/1"
            fps_num, fps_den = map(int, fps_str.split("/"))
            if fps_den == 0:
                return 30.0
            fps = fps_num / fps_den
            return fps if fps > 0 else 30.0
        except Exception as e:
            logger.warning(f"Failed to get video fps for {video}: {e}, using 30fps fallback")
            return 30.0
    

    def _get_video_duration(self, video: str) -> float:
        """Get video duration in seconds"""
        try:
            probe = ffmpeg.probe(video)
            duration = float(probe['format']['duration'])
            return duration
        except Exception as e:
            logger.warning(f"Failed to get video duration: {e}")
            return 0.0
    
    def _get_audio_duration(self, audio: str) -> float:
        """Get audio duration in seconds"""
        try:
            probe = ffmpeg.probe(audio)
            duration = float(probe['format']['duration'])
            return duration
        except Exception as e:
            logger.warning(f"Failed to get audio duration: {e}, using estimate")
            # Fallback: estimate based on file size (very rough)
            import os
            file_size = os.path.getsize(audio)
            # Assume ~16kbps for MP3, so 2KB per second
            estimated_duration = file_size / 2000
            return max(1.0, estimated_duration)  # At least 1 second
    
    def has_audio_stream(self, video: str) -> bool:
        """
        Check if video has audio stream
        
        Args:
            video: Video file path
        
        Returns:
            True if video has audio stream, False otherwise
        """
        try:
            probe = ffmpeg.probe(video)
            audio_streams = [s for s in probe.get('streams', []) if s['codec_type'] == 'audio']
            has_audio = len(audio_streams) > 0
            logger.debug(f"Video {video} has_audio={has_audio}")
            return has_audio
        except Exception as e:
            logger.warning(f"Failed to probe video audio streams: {e}, assuming no audio")
            return False
    

    def _get_media_dimensions(self, media_path: str) -> tuple[int, int]:
        """Read media dimensions with a safe fallback."""
        try:
            probe = ffmpeg.probe(media_path)
            stream = next(s for s in probe["streams"] if s["codec_type"] == "video")
            width = int(stream.get("width") or 1080)
            height = int(stream.get("height") or 1920)
            return width, height
        except Exception as exc:
            logger.warning(f"Failed to read media dimensions for {media_path}: {exc}")
            return 1080, 1920


    def _get_unique_temp_path(self, prefix: str, original_filename: str) -> str:
        """
        Generate unique temporary file path to avoid concurrent conflicts
        
        Args:
            prefix: Prefix for the temp file (e.g., "trimmed", "padded", "black_pad")
            original_filename: Original filename to preserve in temp path
        
        Returns:
            Unique temporary file path with format: temp/{prefix}_{uuid}_{original_filename}
        
        Example:
            >>> self._get_unique_temp_path("trimmed", "video.mp4")
            >>> # Returns: "temp/trimmed_a3f2d8c1_video.mp4"
        """
        from morpheus_video_studio.utils.os_util import get_temp_path
        
        unique_id = uuid.uuid4().hex[:8]
        return get_temp_path(f"{prefix}_{unique_id}_{original_filename}")
    
