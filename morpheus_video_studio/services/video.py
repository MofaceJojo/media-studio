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
Video Processing Service

High-performance video composition service built on ffmpeg-python.

Features:
- Video concatenation
- Audio/video merging
- Background music addition
- Image to video conversion

Note: Requires FFmpeg to be installed on the system.
"""

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


XFADES = {
    "fade",
    "fadeblack",
    "fadewhite",
    "fadefast",
    "fadeslow",
    "dissolve",
    "wipeleft",
    "wiperight",
    "wipeup",
    "wipedown",
    "slideleft",
    "slideright",
    "slideup",
    "slidedown",
    "circleopen",
    "circleclose",
    "circlecrop",
    "rectcrop",
    "zoomin",
    "smoothleft",
    "smoothright",
    "smoothup",
    "smoothdown",
    "coverleft",
    "coverright",
    "coverup",
    "coverdown",
    "revealleft",
    "revealright",
    "revealup",
    "revealdown",
}


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


class VideoService:
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

    def concat_videos(
        self,
        videos: List[str],
        output: str,
        method: Literal["demuxer", "filter"] = "demuxer",
        audio_tracks: Optional[List[str]] = None,
        bgm_path: Optional[str] = None,
        bgm_volume: float = 0.2,
        bgm_mode: Literal["once", "loop"] = "loop",
        transition: str = "none",
        transition_choices: Optional[List[str]] = None,
        transition_duration: float = 0.5,
        transition_audio_delay: float = 0.0,
    ) -> str:
        """
        Concatenate multiple videos into one

        Args:
            videos: List of video file paths to concatenate
            output: Output video file path
            method: Concatenation method
                - "demuxer": Fast, no re-encoding (requires identical formats)
                - "filter": Slower but handles different formats
            bgm_path: Background music file path (optional)
                - None: No BGM
        """
        self._ensure_ffmpeg()

        if not videos:
            raise ValueError("Videos list cannot be empty")
        
        if len(videos) == 1:
            if bgm_path:
                logger.info(f"Only one video provided, adding BGM directly to {output}")
                return self._add_bgm_to_video(
                    video=videos[0],
                    bgm_path=bgm_path,
                    output=output,
                    volume=bgm_volume,
                    mode=bgm_mode,
                )
            logger.info(f"Only one video provided, copying to {output}")
            shutil.copy(videos[0], output)
            return output
        
        logger.info(f"Concatenating {len(videos)} videos using {method} method")
        
        # Step 1: Concatenate videos
        if bgm_path:
            # If BGM needed, concatenate to temp file first
            temp_output = output.replace('.mp4', '_no_bgm.mp4')
            concat_result = (
                self._concat_xfade(
                    videos,
                    temp_output,
                    transition_duration,
                    transition,
                    transition_choices,
                    transition_audio_delay,
                    audio_tracks,
                )
                if self._should_use_xfade(transition, transition_choices)
                else self._concat_demuxer(videos, temp_output) if method == "demuxer"
                else self._concat_filter(videos, temp_output)
            )
            
            # Step 2: Add BGM
            logger.info(f"Adding BGM: {bgm_path} (volume={bgm_volume}, mode={bgm_mode})")
            final_result = self._add_bgm_to_video(
                video=concat_result,
                bgm_path=bgm_path,
                output=output,
                volume=bgm_volume,
                mode=bgm_mode
            )
            
            # Clean up temp file
            if os.path.exists(temp_output):
                os.unlink(temp_output)
            
            return final_result
        else:
            # No BGM, direct concatenation
            if self._should_use_xfade(transition, transition_choices):
                return self._concat_xfade(
                    videos,
                    output,
                    transition_duration,
                    transition,
                    transition_choices,
                    transition_audio_delay,
                    audio_tracks,
                )
            if method == "demuxer":
                return self._concat_demuxer(videos, output)
            else:
                return self._concat_filter(videos, output)

    def _concat_xfade(
        self,
        videos: List[str],
        output: str,
        duration: float = 0.5,
        transition: str = "fade",
        transition_choices: Optional[List[str]] = None,
        audio_delay: float = 0.0,
        audio_tracks: Optional[List[str]] = None,
    ) -> str:
        """Concatenate clips with video xfade and sequential narration audio."""
        if len(videos) < 2:
            shutil.copy(videos[0], output)
            return output

        inputs = [ffmpeg.input(video) for video in videos]
        durations = [self._get_video_duration(video) for video in videos]
        fps_values = [self._get_video_fps(video) for video in videos]
        target_fps = max(24, round(max(fps_values) if fps_values else 30))
        fade_duration = max(0.1, min(duration, min(durations) / 3))

        def normalize_video(stream):
            return (
                stream
                .filter("fps", fps=target_fps)
                .filter("settb", "AVTB")
                .filter("setpts", "PTS-STARTPTS")
            )

        video_stream = normalize_video(inputs[0].video)
        offset = durations[0] - fade_duration
        transition_sequence = self._build_transition_sequence(
            videos=videos,
            transition=transition,
            transition_choices=transition_choices,
        )

        for index in range(1, len(inputs)):
            video_stream = ffmpeg.filter(
                [video_stream, normalize_video(inputs[index].video)],
                "xfade",
                transition=transition_sequence[index - 1],
                duration=fade_duration,
                offset=max(0, offset),
            )
            offset += durations[index] - fade_duration

        pause_duration = max(0.0, float(audio_delay or 0.0))

        # Keep audio sequential to avoid narration overlap. Extend the visual
        # tail to compensate for xfade's overlap plus the intentional pause
        # before the next narration starts.
        boundary_count = max(len(inputs) - 1, 0)
        tail_padding = (fade_duration + pause_duration) * boundary_count
        if tail_padding > 0:
            video_stream = video_stream.filter("tpad", stop_mode="clone", stop_duration=tail_padding)

        try:
            with tempfile.TemporaryDirectory(prefix="mvs_xfade_") as temp_dir:
                temp_dir_path = Path(temp_dir)
                video_only_path = temp_dir_path / "xfade_video.mp4"
                audio_track_path = temp_dir_path / "sequential_audio.wav"

                (
                    ffmpeg.output(
                        video_stream,
                        str(video_only_path),
                        vcodec="libx264",
                        pix_fmt="yuv420p",
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )

                self._build_sequential_audio_track(
                    videos=videos,
                    output=str(audio_track_path),
                    pause_duration=pause_duration,
                    temp_dir=temp_dir_path,
                    audio_tracks=audio_tracks,
                )
                self.merge_audio_video(
                    str(video_only_path),
                    str(audio_track_path),
                    output,
                    replace_audio=True,
                    auto_adjust_duration=True,
                    duration_tolerance=0.05,
                )
            return output
        except ffmpeg.Error as exc:
            error_msg = exc.stderr.decode() if exc.stderr else str(exc)
            raise RuntimeError(f"Failed to concatenate videos with fade transition: {error_msg}")
        except Exception as exc:
            raise RuntimeError(f"Failed to concatenate videos with fade transition: {exc}") from exc

    def _build_sequential_audio_track(
        self,
        videos: List[str],
        output: str,
        pause_duration: float,
        temp_dir: Path,
        audio_tracks: Optional[List[str]] = None,
    ) -> str:
        audio_files: List[Path] = []

        for index, video in enumerate(videos):
            audio_path = temp_dir / f"audio_{index:02d}.wav"
            preferred_audio = audio_tracks[index] if audio_tracks and index < len(audio_tracks) else None
            if preferred_audio:
                self._normalize_audio_file(audio=preferred_audio, output=str(audio_path))
            else:
                self._extract_or_synthesize_audio(video=video, output=str(audio_path))
            audio_files.append(audio_path)

            if index < len(videos) - 1 and pause_duration > 0:
                silence_path = temp_dir / f"silence_{index:02d}.wav"
                self._generate_silence_audio(str(silence_path), pause_duration)
                audio_files.append(silence_path)

        return self._concat_audio_files(audio_files, output)

    def _normalize_audio_file(self, audio: str, output: str) -> str:
        (
            ffmpeg.output(
                ffmpeg.input(audio).audio.filter("aresample", 48000),
                output,
                acodec="pcm_s16le",
                ac=1,
                ar=48000,
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output

    def _extract_or_synthesize_audio(self, video: str, output: str) -> str:
        if not self.has_audio_stream(video):
            self._generate_silence_audio(output, self._get_video_duration(video))
            return output

        (
            ffmpeg.output(
                ffmpeg.input(video).audio.filter("aresample", 48000),
                output,
                acodec="pcm_s16le",
                ac=1,
                ar=48000,
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output

    def _generate_silence_audio(self, output: str, duration: float) -> str:
        (
            ffmpeg.output(
                ffmpeg.input(
                    f"anullsrc=r=48000:cl=mono",
                    f="lavfi",
                    t=max(duration, 0.0),
                ).audio,
                output,
                acodec="pcm_s16le",
                ac=1,
                ar=48000,
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output

    def _concat_audio_files(self, audio_files: List[Path], output: str) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            suffix=".txt",
            encoding="utf-8",
        ) as file_list:
            for audio_file in audio_files:
                abs_path = audio_file.absolute()
                escaped_path = str(abs_path).replace("'", "'\\''")
                file_list.write(f"file '{escaped_path}'\n")
            file_list_path = file_list.name

        try:
            (
                ffmpeg
                .input(file_list_path, format="concat", safe=0)
                .output(output, c="copy")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            return output
        finally:
            if os.path.exists(file_list_path):
                os.unlink(file_list_path)

    def _should_use_xfade(self, transition: str, transition_choices: Optional[List[str]] = None) -> bool:
        if transition in XFADES:
            return True
        if transition in {"random", "sequence"}:
            return bool([item for item in (transition_choices or []) if item in XFADES])
        return False

    def _build_transition_sequence(
        self,
        videos: List[str],
        transition: str,
        transition_choices: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Resolve one transition per boundary between clips.
        """
        count = max(len(videos) - 1, 0)
        choices = [item for item in (transition_choices or []) if item in XFADES]
        if transition in XFADES:
            return [transition] * count
        if not choices:
            return ["fade"] * count
        if transition == "sequence":
            return [choices[idx % len(choices)] for idx in range(count)]
        if transition == "random":
            seed_source = "|".join(videos + choices)
            seed = int(hashlib.md5(seed_source.encode("utf-8")).hexdigest()[:8], 16)
            rng = random.Random(seed)
            return [rng.choice(choices) for _ in range(count)]
        return ["fade"] * count

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
    
    def _concat_demuxer(self, videos: List[str], output: str) -> str:
        """
        Concatenate using concat demuxer (fast, no re-encoding)
        
        FFmpeg equivalent:
            ffmpeg -f concat -safe 0 -i filelist.txt -c copy output.mp4
        """
        # Create temporary file list
        with tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            suffix='.txt',
            encoding='utf-8'
        ) as f:
            for video in videos:
                abs_path = Path(video).absolute()
                escaped_path = str(abs_path).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
            filelist = f.name
        
        try:
            logger.debug(f"Created filelist: {filelist}")
            (
                ffmpeg
                .input(filelist, format='concat', safe=0)
                .output(output, c='copy')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            logger.success(f"Videos concatenated successfully: {output}")
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg concat error: {error_msg}")
            raise RuntimeError(f"Failed to concatenate videos: {error_msg}")
        finally:
            if os.path.exists(filelist):
                os.unlink(filelist)
    
    def _concat_filter(self, videos: List[str], output: str) -> str:
        """
        Concatenate using concat filter (slower but handles different formats)
        
        FFmpeg equivalent:
            ffmpeg -i v1.mp4 -i v2.mp4 -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]"
                   -map "[v]" -map "[a]" output.mp4
        """
        try:
            # Build filter_complex string manually
            n = len(videos)
            
            # Build input stream labels: [0:v][0:a][1:v][1:a]...
            stream_spec = "".join([f"[{i}:v][{i}:a]" for i in range(n)])
            filter_complex = f"{stream_spec}concat=n={n}:v=1:a=1[v][a]"
            
            # Build ffmpeg command
            cmd = ['ffmpeg']
            for video in videos:
                cmd.extend(['-i', video])
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[v]',
                '-map', '[a]',
                '-y',  # Overwrite output
                output
            ])
            
            # Run command
            import subprocess
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.success(f"Videos concatenated successfully: {output}")
            return output
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            logger.error(f"FFmpeg concat filter error: {error_msg}")
            raise RuntimeError(f"Failed to concatenate videos: {error_msg}")
        except Exception as e:
            logger.error(f"Concatenation error: {e}")
            raise RuntimeError(f"Failed to concatenate videos: {e}")
    
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
    
    def merge_audio_video(
        self,
        video: str,
        audio: str,
        output: str,
        replace_audio: bool = True,
        audio_volume: float = 1.0,
        video_volume: float = 0.0,
        pad_strategy: str = "freeze",  # "freeze" (freeze last frame) or "black" (black screen)
        auto_adjust_duration: bool = True,  # Automatically adjust video duration to match audio
        duration_tolerance: float = 0.3,  # Tolerance for video being longer than audio (seconds)
    ) -> str:
        """
        Merge audio with video with intelligent duration adjustment
        
        Automatically handles duration mismatches between video and audio:
        - If video < audio: Pad video to match audio (avoid black screen)
        - If video > audio (within tolerance): Keep as-is (acceptable)
        - If video > audio (exceeds tolerance): Trim video to match audio
        
        Automatically handles videos with or without audio streams.
        - If video has no audio: adds the audio track
        - If video has audio and replace_audio=True: replaces with new audio
        - If video has audio and replace_audio=False: mixes both audio tracks
        
        Args:
            video: Video file path
            audio: Audio file path
            output: Output video file path
            replace_audio: If True, replace video's audio; if False, mix with original
            audio_volume: Volume of the new audio (0.0 to 1.0+)
            video_volume: Volume of original video audio (0.0 to 1.0+)
                         Only used when replace_audio=False
            pad_strategy: Strategy to pad video if audio is longer
                         - "freeze": Freeze last frame (default)
                         - "black": Fill with black screen
            auto_adjust_duration: Enable intelligent duration adjustment (default: True)
            duration_tolerance: Tolerance for video being longer than audio in seconds (default: 0.3)
                              Videos within this tolerance won't be trimmed
        
        Returns:
            Path to the output video file
        
        Raises:
            RuntimeError: If FFmpeg execution fails
        
        Note:
            - Uses the longer duration between video and audio
            - When audio is longer, video is padded using pad_strategy
            - When video is longer, audio is looped or extended
            - Automatically detects if video has audio
            - When video is silent, audio is added regardless of replace_audio
            - When replace_audio=True and video has audio, original audio is removed
            - When replace_audio=False and video has audio, original and new audio are mixed
        """
        self._ensure_ffmpeg()

        # Get durations of video and audio
        video_duration = self._get_video_duration(video)
        audio_duration = self._get_audio_duration(audio)
        
        logger.info(f"Video duration: {video_duration:.2f}s, Audio duration: {audio_duration:.2f}s")
        
        # Intelligent duration adjustment (if enabled)
        if auto_adjust_duration:
            diff = video_duration - audio_duration
            
            if diff < 0:
                # Video shorter than audio → Must pad to avoid black screen
                logger.warning(f"⚠️ Video shorter than audio by {abs(diff):.2f}s, padding required")
                video = self._pad_video_to_duration(video, audio_duration, pad_strategy)
                video_duration = audio_duration  # Update duration after padding
                logger.info(f"📌 Padded video to {audio_duration:.2f}s")
            
            elif diff > duration_tolerance:
                # Video significantly longer than audio → Trim
                logger.info(f"⚠️ Video longer than audio by {diff:.2f}s (tolerance: {duration_tolerance}s)")
                video = self._trim_video_to_duration(video, audio_duration)
                video_duration = audio_duration  # Update duration after trimming
                logger.info(f"✂️ Trimmed video to {audio_duration:.2f}s")
            
            else:  # 0 <= diff <= duration_tolerance
                # Video slightly longer but within tolerance → Keep as-is
                logger.info(f"✅ Duration acceptable: video={video_duration:.2f}s, audio={audio_duration:.2f}s (diff={diff:.2f}s)")
        
        # Determine target duration (max of both)
        target_duration = max(video_duration, audio_duration)
        logger.info(f"Target output duration: {target_duration:.2f}s")
        
        # Check if video has audio stream
        video_has_audio = self.has_audio_stream(video)
        
        # Prepare video stream (potentially with padding)
        input_video = ffmpeg.input(video)
        video_stream = input_video.video
        
        # Pad video if audio is longer
        if audio_duration > video_duration:
            pad_duration = audio_duration - video_duration
            logger.info(f"Audio is longer, padding video by {pad_duration:.2f}s using '{pad_strategy}' strategy")
            
            if pad_strategy == "freeze":
                # Freeze last frame: tpad filter
                video_stream = video_stream.filter('tpad', stop_mode='clone', stop_duration=pad_duration)
            else:  # black
                # Generate black frames for padding duration
                # Get video properties
                probe = ffmpeg.probe(video)
                video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
                width = int(video_info['width'])
                height = int(video_info['height'])
                fps_str = video_info['r_frame_rate']
                fps_num, fps_den = map(int, fps_str.split('/'))
                fps = fps_num / fps_den if fps_den != 0 else 30
                
                # Create black video for padding
                black_video_path = self._get_unique_temp_path("black_pad", os.path.basename(output))
                black_input = ffmpeg.input(
                    f'color=c=black:s={width}x{height}:r={fps}',
                    f='lavfi',
                    t=pad_duration
                )
                
                # Concatenate original video with black padding
                video_stream = ffmpeg.concat(video_stream, black_input.video, v=1, a=0)
        
        # Prepare audio stream (pad if needed to match target duration)
        input_audio = ffmpeg.input(audio)
        audio_stream = input_audio.audio.filter('volume', audio_volume)
        
        # Pad audio with silence if video is longer
        if video_duration > audio_duration:
            pad_duration = video_duration - audio_duration
            logger.info(f"Video is longer, padding audio with {pad_duration:.2f}s silence")
            # Use apad to add silence at the end
            audio_stream = audio_stream.filter('apad', whole_dur=target_duration)
        
        if not video_has_audio:
            logger.info(f"Video has no audio stream, adding audio track")
            # Video is silent, just add the audio
            try:
                (
                    ffmpeg
                    .output(
                        video_stream,
                        audio_stream,
                        output,
                        vcodec='libx264',  # Re-encode video if padded
                        acodec='aac',
                        audio_bitrate='192k'
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                
                logger.success(f"Audio added to silent video: {output}")
                return output
            except ffmpeg.Error as e:
                error_msg = e.stderr.decode() if e.stderr else str(e)
                logger.error(f"FFmpeg error adding audio to silent video: {error_msg}")
                raise RuntimeError(f"Failed to add audio to video: {error_msg}")
        
        # Video has audio, proceed with merging
        logger.info(f"Merging audio with video (replace={replace_audio})")
        
        try:
            if replace_audio:
                # Replace audio: use only new audio, ignore original
                (
                    ffmpeg
                    .output(
                        video_stream,
                        audio_stream,
                        output,
                        vcodec='libx264',  # Re-encode video if padded
                        acodec='aac',
                        audio_bitrate='192k'
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            else:
                # Mix audio: combine original and new audio
                mixed_audio = ffmpeg.filter(
                    [
                        input_video.audio.filter('volume', video_volume),
                        audio_stream
                    ],
                    'amix',
                    inputs=2,
                    duration='longest'  # Use longest audio
                )
                
                (
                    ffmpeg
                    .output(
                        video_stream,
                        mixed_audio,
                        output,
                        vcodec='libx264',  # Re-encode video if padded
                        acodec='aac',
                        audio_bitrate='192k'
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            
            logger.success(f"Audio merged successfully: {output}")
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg merge error: {error_msg}")
            raise RuntimeError(f"Failed to merge audio and video: {error_msg}")
    
    def overlay_image_on_video(
        self,
        video: str,
        overlay_image: str,
        output: str,
        scale_mode: str = "contain",
        motion_mode: str = "none",
        motion_choices: Optional[List[str]] = None,
        motion_seed: int = 0,
    ) -> str:
        """
        Overlay a transparent image on top of video
        
        Args:
            video: Base video file path
            overlay_image: Transparent overlay image path (e.g., rendered HTML with transparent background)
            output: Output video file path
            scale_mode: How to scale the base video to fit the overlay size
                - "contain": Scale video to fit within overlay dimensions (letterbox/pillarbox)
                - "cover": Scale video to cover overlay dimensions (may crop)
                - "stretch": Stretch video to exact overlay dimensions
            motion_mode: Motion preset to apply to video-backed segments before overlay
            motion_choices: Candidate motion presets when using random/sequence modes
            motion_seed: Stable per-segment seed for deterministic motion choice
        
        Returns:
            Path to the output video file
        
        Raises:
            RuntimeError: If FFmpeg execution fails
        
        Note:
            - Overlay image should have transparent background
            - Video is scaled to match overlay dimensions based on scale_mode
            - Final video size matches overlay image size
            - Video codec is re-encoded to support overlay
        """
        self._ensure_ffmpeg()
        logger.info(f"Overlaying image on video (scale_mode={scale_mode})")
        
        try:
            # Get overlay image dimensions
            overlay_probe = ffmpeg.probe(overlay_image)
            overlay_stream = next(s for s in overlay_probe['streams'] if s['codec_type'] == 'video')
            overlay_width = int(overlay_stream['width'])
            overlay_height = int(overlay_stream['height'])
            
            logger.debug(f"Overlay dimensions: {overlay_width}x{overlay_height}")
            
            input_video = ffmpeg.input(video)
            input_overlay = ffmpeg.input(overlay_image)
            
            # Scale video to fit overlay size using scale_mode
            if scale_mode == "contain":
                # Scale to fit (letterbox/pillarbox if aspect ratio differs)
                # Use scale filter with force_original_aspect_ratio=decrease and pad to center
                scaled_video = (
                    input_video
                    .filter('scale', overlay_width, overlay_height, force_original_aspect_ratio='decrease')
                    .filter('pad', overlay_width, overlay_height, '(ow-iw)/2', '(oh-ih)/2', color='black')
                )
            elif scale_mode == "cover":
                # Scale to cover (crop if aspect ratio differs)
                scaled_video = (
                    input_video
                    .filter('scale', overlay_width, overlay_height, force_original_aspect_ratio='increase')
                    .filter('crop', overlay_width, overlay_height)
                )
            else:  # stretch
                # Stretch to exact dimensions
                scaled_video = input_video.filter('scale', overlay_width, overlay_height)
            
            motion_video = self._apply_video_motion(
                scaled_video,
                overlay_width,
                overlay_height,
                source_id=video,
                motion_mode=motion_mode,
                motion_choices=motion_choices,
                motion_seed=motion_seed,
            )

            # Overlay the transparent image on top of the scaled video
            output_stream = ffmpeg.overlay(motion_video, input_overlay)
            
            (
                ffmpeg
                .output(output_stream, output, 
                        vcodec='libx264',
                        pix_fmt='yuv420p',
                        preset='medium',
                        crf=23)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            logger.success(f"Image overlaid on video: {output}")
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg overlay error: {error_msg}")
            raise RuntimeError(f"Failed to overlay image on video: {error_msg}")

    def _apply_video_motion(
        self,
        stream,
        width: int,
        height: int,
        source_id: str,
        motion_mode: str = "none",
        motion_choices: Optional[List[str]] = None,
        motion_seed: int = 0,
    ):
        """Apply a subtle camera move to video clips so effect settings also affect video media."""
        preset = self._pick_video_motion_preset(
            source_id,
            motion_mode=motion_mode,
            motion_choices=motion_choices,
            motion_seed=motion_seed,
        )
        if preset["scale"] <= 1.0:
            return stream

        scaled_width = max(2, int(width * preset["scale"]) // 2 * 2)
        scaled_height = max(2, int(height * preset["scale"]) // 2 * 2)

        return (
            stream
            .filter("scale", scaled_width, scaled_height)
            .filter(
                "crop",
                width,
                height,
                preset["x_expr"],
                preset["y_expr"],
            )
        )

    def _pick_video_motion_preset(
        self,
        source_id: str,
        motion_mode: str = "none",
        motion_choices: Optional[List[str]] = None,
        motion_seed: int = 0,
    ) -> dict:
        """Resolve video motion presets using the same mode names as image motion."""
        valid_modes = {"none", "gentle", "float", "cinematic"}
        filtered_choices = [item for item in (motion_choices or []) if item in valid_modes and item != "none"]
        if motion_mode == "random" and filtered_choices:
            seed_source = f"{source_id}|video|{motion_seed}|{'|'.join(filtered_choices)}"
            seed = int(hashlib.md5(seed_source.encode("utf-8")).hexdigest()[:8], 16)
            motion_mode = filtered_choices[seed % len(filtered_choices)]
        elif motion_mode == "sequence" and filtered_choices:
            motion_mode = filtered_choices[motion_seed % len(filtered_choices)]
        elif motion_mode not in valid_modes:
            motion_mode = "float"

        if motion_mode == "none":
            return {
                "name": "static",
                "scale": 1.0,
                "x_expr": "(in_w-out_w)/2",
                "y_expr": "(in_h-out_h)/2",
            }

        range_x = "(in_w-out_w)"
        range_y = "(in_h-out_h)"
        presets_by_mode = {
            "gentle": [
                {
                    "name": "gentle-drift",
                    "scale": 1.05,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.10*sin(t/3.4)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.08*cos(t/3.9)",
                },
                {
                    "name": "gentle-rise",
                    "scale": 1.06,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.08*cos(t/3.2)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.12*sin(t/4.1)",
                },
            ],
            "float": [
                {
                    "name": "float-wide",
                    "scale": 1.10,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.18*sin(t/2.8)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.12*cos(t/3.3)",
                },
                {
                    "name": "float-diagonal",
                    "scale": 1.11,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.16*cos(t/2.5)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.14*sin(t/3.0)",
                },
            ],
            "cinematic": [
                {
                    "name": "cinematic-push",
                    "scale": 1.14,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.22*sin(t/2.4)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.16*cos(t/2.9)",
                },
                {
                    "name": "cinematic-sweep",
                    "scale": 1.16,
                    "x_expr": f"({range_x})/2 + ({range_x})*0.24*cos(t/2.2)",
                    "y_expr": f"({range_y})/2 + ({range_y})*0.18*sin(t/2.7)",
                },
            ],
        }
        presets = presets_by_mode.get(motion_mode, presets_by_mode["float"])
        seed = int(hashlib.md5(f"{source_id}|video-motion".encode("utf-8")).hexdigest()[:8], 16)
        return presets[(seed + motion_seed) % len(presets)]
    
    def create_video_from_image(
        self,
        image: str,
        audio: str,
        output: str,
        fps: int = 30,
        motion_mode: str = "float",
        motion_choices: Optional[List[str]] = None,
        motion_seed: int = 0,
        min_duration: float = 0.0,
        trailing_silence: float = 0.0,
    ) -> str:
        """
        Create video from static image and audio
        
        Args:
            image: Image file path
            audio: Audio file path
            output: Output video path
            fps: Frames per second
        
        Returns:
            Path to the output video
        
        Raises:
            RuntimeError: If FFmpeg execution fails
        
        Note:
            - Image is displayed as static frame for the duration of audio
            - Video duration matches audio duration
            - Useful for creating video segments from storyboard frames
        
        Example:
            >>> compositor.create_video_from_image(
            ...     "frame.png",
            ...     "narration.mp3",
            ...     "segment.mp4"
            ... )
        """
        self._ensure_ffmpeg()
        logger.info("Creating video from image and audio")
        
        try:
            # Get audio duration to ensure exact video duration match
            probe = ffmpeg.probe(audio)
            audio_duration = float(probe['format']['duration'])
            target_duration = max(
                audio_duration + float(trailing_silence or 0),
                float(min_duration or 0),
            )
            logger.debug(f"Audio duration: {audio_duration:.3f}s, target duration: {target_duration:.3f}s")

            image_width, image_height = self._get_media_dimensions(image)
            motion_preset = self._pick_image_motion_preset(
                image,
                motion_mode,
                motion_choices=motion_choices,
                motion_seed=motion_seed,
            )
            logger.debug(
                f"Image motion preset: {motion_preset['name']} (mode={motion_mode}) for {image_width}x{image_height}"
            )

            # Input image with loop (loop=1 means loop indefinitely)
            input_image = ffmpeg.input(image, loop=1, framerate=fps)
            input_audio = ffmpeg.input(audio)
            audio_stream = input_audio.audio
            if target_duration > audio_duration:
                audio_stream = audio_stream.filter("apad", whole_dur=target_duration)

            motion_stream = input_image.video.filter(
                "zoompan",
                z=motion_preset["zoom_expr"],
                x=motion_preset["x_expr"],
                y=motion_preset["y_expr"],
                d=1,
                s=f"{image_width}x{image_height}",
                fps=fps,
            )

            # Add a gentle fade at scene edges so image segments feel less abrupt.
            fade_time = min(0.35, max(audio_duration * 0.12, 0.15))
            if audio_duration > fade_time * 2:
                motion_stream = motion_stream.filter("fade", type="in", start_time=0, duration=fade_time)
                motion_stream = motion_stream.filter(
                    "fade",
                    type="out",
                    start_time=max(target_duration - fade_time, 0),
                    duration=fade_time,
                )

            (
                ffmpeg
                .output(
                    motion_stream,
                    audio_stream,
                    output,
                    t=target_duration,
                    vcodec='libx264',
                    acodec='aac',
                    pix_fmt='yuv420p',
                    audio_bitrate='192k',
                    preset='medium',
                    crf=23,
                    **{'b:v': '2M'}  # Video bitrate
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            logger.success(f"Video created from image: {output} (duration: {target_duration:.3f}s)")
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg error creating video from image: {error_msg}")
            raise RuntimeError(f"Failed to create video from image: {error_msg}")

    def create_video_from_images(
        self,
        images: List[str],
        audio: str,
        output: str,
        fps: int = 30,
        motion_mode: str = "float",
        motion_choices: Optional[List[str]] = None,
        motion_seed: int = 0,
        min_duration: float = 0.0,
        trailing_silence: float = 0.0,
    ) -> str:
        """Create one narration segment from multiple still images."""
        self._ensure_ffmpeg()
        valid_images = [image for image in images if image]
        if not valid_images:
            raise ValueError("Images list cannot be empty")
        if len(valid_images) == 1:
            return self.create_video_from_image(
                image=valid_images[0],
                audio=audio,
                output=output,
                fps=fps,
                motion_mode=motion_mode,
                motion_choices=motion_choices,
                motion_seed=motion_seed,
                min_duration=min_duration,
                trailing_silence=trailing_silence,
            )

        from morpheus_video_studio.utils.content_generators import plan_visual_shots

        audio_duration = self._get_audio_duration(audio)
        target_duration = max(
            audio_duration + float(trailing_silence or 0.0),
            float(min_duration or 0.0),
        )
        shot_plan = plan_visual_shots(
            target_duration,
            min_shot_seconds=2.4,
            max_shot_seconds=4.2,
            max_shots=min(3, len(valid_images)),
        )
        selected_images = valid_images[: shot_plan["shot_count"]]

        with tempfile.TemporaryDirectory(prefix="mvs_multishot_") as temp_dir:
            temp_dir_path = Path(temp_dir)
            shot_videos: List[str] = []
            for index, (image, shot_duration) in enumerate(zip(selected_images, shot_plan["shot_durations"])):
                shot_video_path = temp_dir_path / f"shot_{index + 1:02d}.mp4"
                self.create_silent_video_from_image(
                    image=image,
                    output=str(shot_video_path),
                    duration=shot_duration,
                    fps=fps,
                    motion_mode=motion_mode,
                    motion_choices=motion_choices,
                    motion_seed=motion_seed + index,
                )
                shot_videos.append(str(shot_video_path))

            stitched_video = temp_dir_path / "stitched.mp4"
            padded_audio = temp_dir_path / "narration_padded.m4a"
            internal_transition = min(
                0.35,
                max(min(shot_plan["shot_durations"]) * 0.12, 0.18),
            )
            self.concat_videos(
                shot_videos,
                str(stitched_video),
                method="filter",
                transition="sequence" if len(shot_videos) > 1 else "none",
                transition_choices=["fade", "dissolve", "wipeleft"],
                transition_duration=internal_transition,
                transition_audio_delay=0.0,
            )
            audio_to_merge = audio
            if target_duration > audio_duration:
                (
                    ffmpeg.output(
                        ffmpeg.input(audio).audio.filter("apad", whole_dur=target_duration),
                        str(padded_audio),
                        t=target_duration,
                        acodec="aac",
                        audio_bitrate="192k",
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                audio_to_merge = str(padded_audio)
            self.merge_audio_video(
                video=str(stitched_video),
                audio=audio_to_merge,
                output=output,
                replace_audio=True,
                auto_adjust_duration=True,
                duration_tolerance=0.05,
            )
        return output

    def extract_video_frame(
        self,
        video: str,
        output_image: str,
        timestamp: float = 0.2,
    ) -> str:
        """Extract one representative frame from a video clip."""
        self._ensure_ffmpeg()
        try:
            (
                ffmpeg
                .input(video, ss=max(0.0, float(timestamp)))
                .output(output_image, vframes=1)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            return output_image
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg frame extraction error: {error_msg}")
            raise RuntimeError(f"Failed to extract frame from video: {error_msg}")

    def create_silent_video_from_image(
        self,
        image: str,
        output: str,
        duration: float,
        fps: int = 30,
        motion_mode: str = "float",
        motion_choices: Optional[List[str]] = None,
        motion_seed: int = 0,
    ) -> str:
        """Create a silent motion shot from a still image."""
        self._ensure_ffmpeg()
        try:
            image_width, image_height = self._get_media_dimensions(image)
            motion_preset = self._pick_image_motion_preset(
                image,
                motion_mode,
                motion_choices=motion_choices,
                motion_seed=motion_seed,
            )
            input_image = ffmpeg.input(image, loop=1, framerate=fps)
            motion_stream = input_image.video.filter(
                "zoompan",
                z=motion_preset["zoom_expr"],
                x=motion_preset["x_expr"],
                y=motion_preset["y_expr"],
                d=1,
                s=f"{image_width}x{image_height}",
                fps=fps,
            )
            (
                ffmpeg
                .output(
                    motion_stream,
                    output,
                    t=max(float(duration), 0.1),
                    vcodec="libx264",
                    pix_fmt="yuv420p",
                    preset="medium",
                    crf=23,
                    **{"b:v": "2M"},
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg silent image video error: {error_msg}")
            raise RuntimeError(f"Failed to create silent video from image: {error_msg}")

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

    def _pick_image_motion_preset(
        self,
        image_path: str,
        motion_mode: str = "float",
        motion_choices: Optional[List[str]] = None,
        motion_seed: int = 0,
    ) -> dict:
        """
        Deterministically vary Ken Burns motion so image segments feel alive.
        """
        valid_modes = {"none", "gentle", "float", "cinematic"}
        filtered_choices = [item for item in (motion_choices or []) if item in valid_modes and item != "none"]
        if motion_mode == "random" and filtered_choices:
            seed_source = f"{image_path}|{motion_seed}|{'|'.join(filtered_choices)}"
            seed = int(hashlib.md5(seed_source.encode("utf-8")).hexdigest()[:8], 16)
            motion_mode = filtered_choices[seed % len(filtered_choices)]
        elif motion_mode == "sequence" and filtered_choices:
            motion_mode = filtered_choices[motion_seed % len(filtered_choices)]
        elif motion_mode not in valid_modes:
            motion_mode = "float"

        if motion_mode == "none":
            return {
                "name": "static",
                "zoom_expr": "1",
                "x_expr": "iw/2-(iw/zoom/2)",
                "y_expr": "ih/2-(ih/zoom/2)",
            }

        seed = int(hashlib.md5(image_path.encode("utf-8")).hexdigest()[:8], 16)
        if motion_mode == "gentle":
            presets = [
                {
                    "name": "gentle-zoom-in",
                    "zoom_expr": "min(zoom+0.0012,1.16)",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
                {
                    "name": "gentle-drift-right",
                    "zoom_expr": "min(zoom+0.0011,1.14)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.12*sin(on/42)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.05*cos(on/54)",
                },
                {
                    "name": "gentle-drift-up",
                    "zoom_expr": "min(zoom+0.0011,1.14)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.05*sin(on/50)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.12*cos(on/40)",
                },
                {
                    "name": "gentle-zoom-out",
                    "zoom_expr": "if(eq(on,1),1.16,max(zoom-0.0010,1.03))",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
            ]
        elif motion_mode == "cinematic":
            presets = [
                {
                    "name": "cinematic-zoom-in",
                    "zoom_expr": "min(zoom+0.0018,1.28)",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
                {
                    "name": "cinematic-drift-right",
                    "zoom_expr": "min(zoom+0.0016,1.24)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.22*sin(on/32)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.08*cos(on/44)",
                },
                {
                    "name": "cinematic-drift-up",
                    "zoom_expr": "min(zoom+0.0016,1.24)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.08*sin(on/46)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.22*cos(on/30)",
                },
                {
                    "name": "cinematic-zoom-out",
                    "zoom_expr": "if(eq(on,1),1.26,max(zoom-0.0014,1.04))",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
            ]
        else:
            presets = [
                {
                    "name": "float-zoom-in",
                    "zoom_expr": "min(zoom+0.0014,1.20)",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
                {
                    "name": "float-drift-right",
                    "zoom_expr": "min(zoom+0.0013,1.19)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.18*sin(on/34)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.07*cos(on/46)",
                },
                {
                    "name": "float-drift-up",
                    "zoom_expr": "min(zoom+0.0013,1.19)",
                    "x_expr": "iw/2-(iw/zoom/2)+(iw-iw/zoom)*0.07*sin(on/44)",
                    "y_expr": "ih/2-(ih/zoom/2)+(ih-ih/zoom)*0.18*cos(on/34)",
                },
                {
                    "name": "float-zoom-out",
                    "zoom_expr": "if(eq(on,1),1.20,max(zoom-0.0012,1.04))",
                    "x_expr": "iw/2-(iw/zoom/2)",
                    "y_expr": "ih/2-(ih/zoom/2)",
                },
            ]
        return presets[seed % len(presets)]
    
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
    
    def _trim_video_to_duration(self, video: str, target_duration: float) -> str:
        """
        Trim video to specified duration
        
        Args:
            video: Input video file path
            target_duration: Target duration in seconds
        
        Returns:
            Path to trimmed video (temp file)
        
        Raises:
            RuntimeError: If FFmpeg execution fails
        """
        output = self._get_unique_temp_path("trimmed", os.path.basename(video))
        
        try:
            # Use stream copy when possible for fast trimming
            input_stream = ffmpeg.input(video, t=target_duration)
            output_kwargs = {"vcodec": "copy"}
            if self.has_audio_stream(video):
                output_kwargs["acodec"] = "copy"
            (
                input_stream
                .output(output, **output_kwargs)
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True, quiet=True)
            )
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg error trimming video: {error_msg}")
            raise RuntimeError(f"Failed to trim video: {error_msg}")
    
    def _pad_video_to_duration(self, video: str, target_duration: float, pad_strategy: str = "freeze") -> str:
        """
        Pad video to specified duration by extending the last frame or adding black frames
        
        Args:
            video: Input video file path
            target_duration: Target duration in seconds
            pad_strategy: Padding strategy - "freeze" (freeze last frame) or "black" (black screen)
        
        Returns:
            Path to padded video (temp file)
        
        Raises:
            RuntimeError: If FFmpeg execution fails
        """
        output = self._get_unique_temp_path("padded", os.path.basename(video))
        
        video_duration = self._get_video_duration(video)
        pad_duration = target_duration - video_duration
        
        if pad_duration <= 0:
            # No padding needed, return original
            return video
        
        try:
            input_video = ffmpeg.input(video)
            video_stream = input_video.video
            
            if pad_strategy == "freeze":
                # Freeze last frame using tpad filter
                video_stream = video_stream.filter('tpad', stop_mode='clone', stop_duration=pad_duration)
                
                # Output with re-encoding (tpad requires it)
                (
                    ffmpeg
                    .output(
                        video_stream,
                        output,
                        vcodec='libx264',
                        preset='fast',
                        crf=23
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True, quiet=True)
                )
            else:  # black
                # Generate black frames for padding duration
                # Get video properties
                probe = ffmpeg.probe(video)
                video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
                width = int(video_info['width'])
                height = int(video_info['height'])
                fps_str = video_info['r_frame_rate']
                fps_num, fps_den = map(int, fps_str.split('/'))
                fps = fps_num / fps_den if fps_den != 0 else 30
                
                # Create black video for padding
                black_input = ffmpeg.input(
                    f'color=c=black:s={width}x{height}:r={fps}',
                    f='lavfi',
                    t=pad_duration
                )
                
                # Concatenate original video with black padding
                video_stream = ffmpeg.concat(video_stream, black_input.video, v=1, a=0)
                
                (
                    ffmpeg
                    .output(
                        video_stream,
                        output,
                        vcodec='libx264',
                        preset='fast',
                        crf=23
                    )
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True, quiet=True)
                )
            
            return output
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"FFmpeg error padding video: {error_msg}")
            raise RuntimeError(f"Failed to pad video: {error_msg}")
