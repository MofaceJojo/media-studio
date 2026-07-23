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

"""VideoService facade — composes the concern mixins; public API unchanged."""

from morpheus_video_studio.services.video.probe import MediaProbeMixin, check_ffmpeg
from morpheus_video_studio.services.video.motion import MotionPresetMixin
from morpheus_video_studio.services.video.concat import ConcatMixin, XFADES
from morpheus_video_studio.services.video.segments import SegmentBuilderMixin
from morpheus_video_studio.services.video.bgm import BgmMixin


class VideoService(
    MediaProbeMixin,
    MotionPresetMixin,
    ConcatMixin,
    SegmentBuilderMixin,
    BgmMixin,
):
    """
    Video compositor for common video processing tasks

    Uses ffmpeg-python for high-performance video processing.
    All operations preserve video quality when possible (stream copy).

    Examples:
        >>> compositor = VideoCompositor()
        >>>
        >>> # Concatenate videos
        >>> compositor.concat_videos(
        ...     ["intro.mp4", "main.mp4", "outro.mp4"],
        ...     "final.mp4"
        ... )
        >>>
        >>> # Add voiceover
        >>> compositor.merge_audio_video(
        ...     "visual.mp4",
        ...     "voiceover.mp3",
        ...     "final.mp4"
        ... )
        >>>
        >>> # Add background music
        >>> compositor.add_bgm(
        ...     "video.mp4",
        ...     "music.mp3",
        ...     "final.mp4",
        ...     bgm_volume=0.3
        ... )
        >>>
        >>> # Create video from image + audio
        >>> compositor.create_video_from_image(
        ...     "frame.png",
        ...     "narration.mp3",
        ...     "segment.mp4"
        ... )
    """

    def __init__(self):
        self._ffmpeg_checked = False

    def _ensure_ffmpeg(self):
        """Lazily check FFmpeg availability on first use, not at import time"""
        if not self._ffmpeg_checked:
            check_ffmpeg()
            self._ffmpeg_checked = True
