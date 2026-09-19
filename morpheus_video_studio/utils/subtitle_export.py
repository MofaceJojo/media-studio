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

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from loguru import logger

from morpheus_video_studio.utils.audio_timing import AudioTiming


_PUNCTUATION = frozenset("，、；：。！？,.!?;:")
_PAUSE_WEIGHTS = {
    "，": 0.35,
    "、": 0.35,
    ",": 0.35,
    "：": 0.35,
    ":": 0.35,
    "；": 0.45,
    ";": 0.45,
    "。": 0.7,
    "！": 0.7,
    "？": 0.7,
    ".": 0.7,
    "!": 0.7,
    "?": 0.7,
}


@dataclass(frozen=True)
class SubtitleCue:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class TimelineSegment:
    text: str
    audio_timing: AudioTiming
    timeline_duration: float


def _format_timestamp(seconds: float) -> str:
    """Format seconds as an SRT timestamp (HH:MM:SS,mmm)."""
    total_ms = max(int(round(seconds * 1000)), 0)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _split_phrases(text: str, max_chars: int) -> list[str]:
    """Split on visible punctuation, then hard-wrap without dropping it."""
    visible = "".join((text or "").split())
    if not visible:
        return []
    limit = max(int(max_chars), 1)
    phrases: list[str] = []
    current = ""
    for char in visible:
        current += char
        if char in _PUNCTUATION or len(current) >= limit:
            phrases.append(current)
            current = ""
    if current:
        phrases.append(current)
    return phrases


def _cue_weight(text: str) -> float:
    return len(text) + _PAUSE_WEIGHTS.get(text[-1], 0.0)


def _ordered_minimum_cost_pairs(
    targets: list[float], midpoints: list[float], *, state_count: list[int] | None = None
) -> list[tuple[int, int]]:
    """Match all of the shorter ordered sequence to a minimum-cost subset."""
    if not targets or not midpoints:
        return []

    pauses_are_shorter = len(midpoints) <= len(targets)
    short = midpoints if pauses_are_shorter else targets
    long = targets if pauses_are_shorter else midpoints
    rows, columns = len(short), len(long)
    if state_count is not None:
        state_count[0] += (rows + 1) * (columns + 1)

    infinity = float("inf")
    costs = [[infinity] * (columns + 1) for _ in range(rows + 1)]
    matched = [[False] * (columns + 1) for _ in range(rows + 1)]
    for column in range(columns + 1):
        costs[0][column] = 0.0

    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            skip = costs[row][column - 1]
            match = costs[row - 1][column - 1] + abs(short[row - 1] - long[column - 1])
            if match <= skip:
                costs[row][column] = match
                matched[row][column] = True
            else:
                costs[row][column] = skip

    pairs: list[tuple[int, int]] = []
    row, column = rows, columns
    while row:
        if matched[row][column]:
            short_index, long_index = row - 1, column - 1
            pairs.append(
                (long_index, short_index)
                if pauses_are_shorter
                else (short_index, long_index)
            )
            row -= 1
        column -= 1
    return list(reversed(pairs))


def _pause_boundaries(phrases: list[str], timing: AudioTiming) -> dict[int, float]:
    """Assign ordered phrase boundaries to ordered measured pause midpoints."""
    if len(phrases) < 2 or not timing.pauses:
        return {}
    duration = timing.speech_end - timing.speech_start
    total_weight = sum(_cue_weight(phrase) for phrase in phrases)
    if duration <= 0 or total_weight <= 0:
        return {}

    cumulative = 0.0
    targets: list[float] = []
    for phrase in phrases[:-1]:
        cumulative += _cue_weight(phrase)
        targets.append(timing.speech_start + duration * cumulative / total_weight)
    midpoints = [(start + end) / 2 for start, end in timing.pauses]

    pairs = _ordered_minimum_cost_pairs(targets, midpoints)
    return {boundary + 1: midpoints[pause] for boundary, pause in pairs}


def plan_segment_cues(
    text: str, timing: AudioTiming, *, max_chars: int = 18
) -> list[SubtitleCue]:
    """Plan phrase cues inside an audio clip's measured speech interval."""
    phrases = _split_phrases(text, max_chars)
    speech_duration = timing.speech_end - timing.speech_start
    if not phrases or speech_duration <= 0:
        return []

    boundaries: dict[int, float] = {0: timing.speech_start, len(phrases): timing.speech_end}
    boundaries.update(_pause_boundaries(phrases, timing))
    anchors = sorted(boundaries)
    for left, right in zip(anchors, anchors[1:]):
        interval_weight = sum(_cue_weight(phrase) for phrase in phrases[left:right])
        if interval_weight <= 0:
            continue
        interval_start = boundaries[left]
        interval_duration = boundaries[right] - interval_start
        cursor = interval_start
        for index in range(left + 1, right):
            cursor += interval_duration * _cue_weight(phrases[index - 1]) / interval_weight
            boundaries[index] = cursor

    if len(boundaries) < len(phrases) + 1:
        logger.debug("Using weighted interpolation for unmatched subtitle cue boundaries")
    return [
        SubtitleCue(phrases[index], boundaries[index], boundaries[index + 1])
        for index in range(len(phrases))
    ]


def build_global_cues(
    segments: list[TimelineSegment], *, max_chars: int = 18
) -> list[SubtitleCue]:
    """Offset locally planned cues by every full scene duration."""
    cues: list[SubtitleCue] = []
    cursor = 0.0
    for segment in segments:
        cues.extend(
            SubtitleCue(cue.text, cue.start + cursor, cue.end + cursor)
            for cue in plan_segment_cues(segment.text, segment.audio_timing, max_chars=max_chars)
        )
        cursor += max(float(segment.timeline_duration or 0.0), 0.0)
    return cues


def export_srt_cues(cues: list[SubtitleCue], output_path: str) -> str:
    """Serialize already-planned cues to an SRT file."""
    lines: list[str] = []
    for index, cue in enumerate(cues, start=1):
        lines.extend(
            [
                str(index),
                f"{_format_timestamp(cue.start)} --> {_format_timestamp(cue.end)}",
                cue.text,
                "",
            ]
        )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def export_srt(
    segments: List[Tuple[str, float]],
    output_path: str,
) -> str:
    """Write an SRT file from (narration_text, duration_seconds) segments.

    Segments are laid out back-to-back starting at 0, matching the
    audio-driven concat where every clip keeps its full duration.
    Returns the written path.
    """
    cursor = 0.0
    cues: list[SubtitleCue] = []
    for text, duration in segments:
        clean_text = (text or "").strip()
        duration = max(float(duration or 0.0), 0.0)
        if not clean_text or duration <= 0:
            cursor += duration
            continue
        timing = AudioTiming(duration, 0.0, duration, [])
        cues.extend(
            SubtitleCue(cue.text, cue.start + cursor, cue.end + cursor)
            for cue in plan_segment_cues(clean_text, timing)
        )
        cursor += duration
    return export_srt_cues(cues, output_path)
