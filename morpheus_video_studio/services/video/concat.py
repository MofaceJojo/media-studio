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

"""Video concatenation: demuxer/filter concat and narration-safe crossfades."""

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



class ConcatMixin:
    """Concatenation strategies; xfade pads clip tails so narration survives."""

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
        """Concatenate clips with video xfade and sequential narration audio.

        Narration is rebuilt as a separate sequential track (never crossfaded),
        and the visual tail is extended to compensate for the xfade overlap, so
        the output keeps the full duration of every clip's narration.
        """
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
    
