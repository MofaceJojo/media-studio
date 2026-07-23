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
SRT subtitle export.

The storyboard already knows each narration's text and its real duration
(measured from the generated audio), so an accurate subtitle file is pure
arithmetic — no speech recognition needed. The .srt is written next to the
final video for manual platform uploads (YouTube, Bilibili, etc.).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple


def _format_timestamp(seconds: float) -> str:
    """Format seconds as an SRT timestamp (HH:MM:SS,mmm)."""
    total_ms = max(int(round(seconds * 1000)), 0)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def export_srt(
    segments: List[Tuple[str, float]],
    output_path: str,
) -> str:
    """Write an SRT file from (narration_text, duration_seconds) segments.

    Segments are laid out back-to-back starting at 0, matching the
    audio-driven concat where every clip keeps its full duration.
    Returns the written path.
    """
    lines: List[str] = []
    cursor = 0.0
    cue_index = 0
    for text, duration in segments:
        clean_text = (text or "").strip()
        duration = max(float(duration or 0.0), 0.0)
        if not clean_text or duration <= 0:
            cursor += duration
            continue
        cue_index += 1
        start = cursor
        end = cursor + duration
        lines.append(str(cue_index))
        lines.append(f"{_format_timestamp(start)} --> {_format_timestamp(end)}")
        lines.append(clean_text)
        lines.append("")
        cursor = end

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
