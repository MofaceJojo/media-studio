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
Final-video QA gate.

Runs cheap, local-only checks on a finished video so broken output is
flagged before the user (or a publish pipeline) picks it up:

1. Stream integrity — the file has a decodable video and audio stream.
2. Duration match — actual duration vs. the audio-driven expectation.
3. Frozen picture — long stretches with no visual change (the "one static
   image" failure mode).
4. Dead air — long silent gaps in the narration track.

All checks are warnings, never hard failures: the pipeline still delivers
the file, but the report makes problems visible immediately.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional

from loguru import logger

import ffmpeg


@dataclass
class VideoQAReport:
    """Outcome of the final-video QA gate."""

    video_path: str
    ok: bool = True
    duration_seconds: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def add_warning(self, message: str) -> None:
        self.ok = False
        self.warnings.append(message)


def _run_ffmpeg_filter_scan(video_path: str, video_filter: Optional[str], audio_filter: Optional[str]) -> str:
    """Decode the file through detection filters and return ffmpeg's stderr."""
    command = ["ffmpeg", "-hide_banner", "-nostats", "-i", video_path]
    if video_filter:
        command += ["-vf", video_filter]
    else:
        command += ["-vn"]
    if audio_filter:
        command += ["-af", audio_filter]
    command += ["-f", "null", "-"]
    completed = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=600,
    )
    return completed.stderr or ""


def inspect_final_video(
    video_path: str,
    expected_duration_seconds: Optional[float] = None,
    duration_tolerance_seconds: float = 1.5,
    freeze_threshold_seconds: float = 8.0,
    silence_threshold_seconds: float = 3.0,
) -> VideoQAReport:
    """Run the QA gate on a finished video and return a warning report."""
    report = VideoQAReport(video_path=video_path)

    # 1. Stream integrity + duration via ffprobe
    try:
        probe = ffmpeg.probe(video_path)
    except Exception as exc:
        report.add_warning(f"ffprobe 无法读取成片：{exc}")
        return report

    streams = probe.get("streams", [])
    has_video = any(stream.get("codec_type") == "video" for stream in streams)
    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    if not has_video:
        report.add_warning("成片缺少视频流")
    if not has_audio:
        report.add_warning("成片缺少音频流（旁白丢失）")

    try:
        report.duration_seconds = float(probe["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        report.add_warning("成片时长不可读")
        return report

    # 2. Audio-driven duration match
    if expected_duration_seconds is not None and expected_duration_seconds > 0:
        drift = report.duration_seconds - float(expected_duration_seconds)
        if abs(drift) > duration_tolerance_seconds:
            report.add_warning(
                f"成片时长 {report.duration_seconds:.2f}s 与音频驱动的预期 "
                f"{expected_duration_seconds:.2f}s 偏差 {drift:+.2f}s（容差 ±{duration_tolerance_seconds:.1f}s）"
            )

    # 3 + 4. Frozen picture / dead air in one decode pass
    if has_video or has_audio:
        try:
            stderr = _run_ffmpeg_filter_scan(
                video_path,
                video_filter=(
                    f"freezedetect=n=-60dB:d={freeze_threshold_seconds}" if has_video else None
                ),
                audio_filter=(
                    f"silencedetect=n=-45dB:d={silence_threshold_seconds}" if has_audio else None
                ),
            )
        except Exception as exc:
            report.add_warning(f"冻结帧/静音检测未能运行：{exc}")
            return report

        for match in re.finditer(r"freeze_start:\s*([0-9.]+)", stderr):
            report.add_warning(
                f"画面在 {float(match.group(1)):.1f}s 起持续静止超过 "
                f"{freeze_threshold_seconds:.0f}s（\"一张图不动\"）"
            )

        for match in re.finditer(
            r"silence_start:\s*([0-9.]+)[\s\S]*?silence_duration:\s*([0-9.]+)", stderr
        ):
            start = float(match.group(1))
            duration = float(match.group(2))
            # A short quiet tail is legitimate (fade-out / BGM-free ending),
            # but a long end-reaching silence still means narration was lost.
            reaches_end = start + duration >= report.duration_seconds - 0.5
            if reaches_end and duration <= 5.0:
                continue
            report.add_warning(
                f"音轨在 {start:.1f}s 起出现 {duration:.1f}s 静音段（旁白可能断裂）"
            )

    if report.ok:
        logger.info(f"✅ 成片自检通过: {video_path} ({report.duration_seconds:.2f}s)")
    else:
        for warning in report.warnings:
            logger.warning(f"⚠️ 成片自检: {warning}")
    return report
