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

"""Regression tests for the audio-duration-driven video chain.

Covers:
- concat with fade transitions must preserve total duration (no narration
  gets eaten by the crossfade)
- create_video_from_image must match audio duration exactly
- merge_audio_video must pad video when audio is longer
- FrameProcessor duration probing must fall back to the known audio duration
"""

import asyncio
import shutil
import subprocess

import pytest

from morpheus_video_studio.services.video import VideoService

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

requires_ffmpeg = pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="ffmpeg not installed")


def _make_clip(path, duration, color, tone_hz, size="320x240", fps=30):
    """Generate a solid-color clip with a sine-tone narration track."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"color=c={color}:s={size}:r={fps}:d={duration}",
            "-f", "lavfi", "-i", f"sine=frequency={tone_hz}:sample_rate=44100:duration={duration}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest",
            str(path),
        ],
        check=True,
    )
    return str(path)


def _make_audio(path, duration, tone_hz=440):
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"sine=frequency={tone_hz}:sample_rate=44100:duration={duration}",
            str(path),
        ],
        check=True,
    )
    return str(path)


def _make_image(path, size="320x240"):
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"color=c=red:s={size}:d=0.1",
            "-frames:v", "1",
            str(path),
        ],
        check=True,
    )
    return str(path)


def _probe_duration(path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nk=1:nw=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


@requires_ffmpeg
class TestConcatWithFade:
    def test_fade_concat_preserves_total_duration(self, tmp_path):
        """The crossfade must consume padding, not narration: the output
        duration equals the sum of the inputs (the old behaviour lost
        fade_duration seconds of narration per transition)."""
        clips = [
            _make_clip(tmp_path / "a.mp4", 2.0, "red", 440),
            _make_clip(tmp_path / "b.mp4", 3.0, "blue", 880),
            _make_clip(tmp_path / "c.mp4", 2.0, "green", 660),
        ]
        expected_total = sum(_probe_duration(c) for c in clips)

        output = str(tmp_path / "out.mp4")
        VideoService().concat_videos(clips, output, transition="fade", transition_duration=0.5)

        actual = _probe_duration(output)
        # Old implementation produced expected_total - 2 * 0.5 = ~6.0s
        assert actual == pytest.approx(expected_total, abs=0.25), (
            f"fade concat lost narration time: expected ~{expected_total:.2f}s, got {actual:.2f}s"
        )

    def test_fade_concat_two_clips(self, tmp_path):
        clips = [
            _make_clip(tmp_path / "a.mp4", 2.0, "red", 440),
            _make_clip(tmp_path / "b.mp4", 2.0, "blue", 880),
        ]
        expected_total = sum(_probe_duration(c) for c in clips)

        output = str(tmp_path / "out.mp4")
        VideoService().concat_videos(clips, output, transition="fade", transition_duration=0.5)

        assert _probe_duration(output) == pytest.approx(expected_total, abs=0.25)

    def test_plain_concat_still_works(self, tmp_path):
        clips = [
            _make_clip(tmp_path / "a.mp4", 1.0, "red", 440),
            _make_clip(tmp_path / "b.mp4", 1.0, "blue", 880),
        ]
        output = str(tmp_path / "out.mp4")
        VideoService().concat_videos(clips, output, transition="none")
        assert _probe_duration(output) == pytest.approx(2.0, abs=0.25)


@requires_ffmpeg
class TestAudioDrivenDuration:
    def test_video_from_image_matches_audio_duration(self, tmp_path):
        image = _make_image(tmp_path / "frame.png")
        audio = _make_audio(tmp_path / "narration.mp3", 2.5)

        output = str(tmp_path / "segment.mp4")
        VideoService().create_video_from_image(image, audio, output)

        assert _probe_duration(output) == pytest.approx(2.5, abs=0.2)

    def test_merge_pads_video_when_audio_longer(self, tmp_path):
        video = _make_clip(tmp_path / "v.mp4", 2.0, "red", 440)
        audio = _make_audio(tmp_path / "a.mp3", 3.0)

        output = str(tmp_path / "out.mp4")
        VideoService().merge_audio_video(video, audio, output, replace_audio=True)

        assert _probe_duration(output) == pytest.approx(3.0, abs=0.25)

    def test_merge_trims_video_when_much_longer_than_audio(self, tmp_path):
        video = _make_clip(tmp_path / "v.mp4", 4.0, "red", 440)
        audio = _make_audio(tmp_path / "a.mp3", 2.0)

        output = str(tmp_path / "out.mp4")
        VideoService().merge_audio_video(video, audio, output, replace_audio=True)

        assert _probe_duration(output) == pytest.approx(2.0, abs=0.35)


class TestFrameProcessorDurationFallback:
    def test_probe_failure_falls_back_to_known_duration(self):
        from morpheus_video_studio.services.frame_processor import FrameProcessor

        processor = FrameProcessor(morpheus_video_studio_core=None)
        duration = asyncio.run(
            processor._get_video_duration("/nonexistent/video.mp4", fallback=7.5)
        )
        assert duration == 7.5

    def test_probe_failure_without_fallback_defaults_to_one_second(self):
        from morpheus_video_studio.services.frame_processor import FrameProcessor

        processor = FrameProcessor(morpheus_video_studio_core=None)
        duration = asyncio.run(processor._get_video_duration("/nonexistent/video.mp4"))
        assert duration == 1.0
