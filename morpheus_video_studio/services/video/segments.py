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

"""Per-narration segment builders: stills to motion video, overlays, A/V merge."""

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


class SegmentBuilderMixin:
    """Builds one narration segment from images/video plus narration audio."""

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
        shot_min_seconds: float = 2.4,
        shot_max_seconds: float = 4.2,
        shot_max_count: int = 3,
        shot_hard_max_hold_seconds: Optional[float] = None,
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
            min_shot_seconds=shot_min_seconds,
            max_shot_seconds=shot_max_seconds,
            max_shots=min(shot_max_count, len(valid_images)),
            hard_max_hold_seconds=shot_hard_max_hold_seconds,
        )
        # Cycle images when the plan needs more shots than we have stills, so
        # every planned duration keeps a visual and total length stays equal
        # to the narration (a truncating zip here would desync audio/video).
        selected_images = [
            valid_images[index % len(valid_images)]
            for index in range(shot_plan["shot_count"])
        ]

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
