# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");

"""Audio silence detection used to place subtitles in spoken intervals."""

from __future__ import annotations

from dataclasses import dataclass
import re
import subprocess

from loguru import logger


@dataclass(frozen=True)
class AudioTiming:
    """Measured speech window and pauses for one narration clip."""

    duration: float
    speech_start: float
    speech_end: float
    pauses: list[tuple[float, float]]


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_SILENCE_START_RE = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")


def _parse_duration(output: str) -> float:
    match = _DURATION_RE.search(output)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def detect_audio_timing(audio_path: str, *, min_silence: float = 0.12) -> AudioTiming:
    """Measure speech bounds and silence intervals with FFmpeg's silencedetect."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            audio_path,
            "-af",
            f"silencedetect=noise=-35dB:d={min_silence}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (getattr(result, "stderr", "") or "") + "\n" + (getattr(result, "stdout", "") or "")
    duration = _parse_duration(output)
    starts = [float(value) for value in _SILENCE_START_RE.findall(output)]
    ends = [float(value) for value in _SILENCE_END_RE.findall(output)]
    silences = list(zip(starts, ends))

    if duration <= 0:
        logger.warning("Could not measure audio duration for {}; no subtitle cues will be planned", audio_path)
        return AudioTiming(0.0, 0.0, 0.0, [])

    speech_start = 0.0
    speech_end = duration
    if silences and silences[0][0] <= 0.01:
        speech_start = min(max(silences[0][1], 0.0), duration)
        silences = silences[1:]
    if silences and silences[-1][1] >= duration - 0.01:
        speech_end = min(max(silences[-1][0], 0.0), duration)
        silences = silences[:-1]

    pauses = [
        (start, end)
        for start, end in silences
        if speech_start < start < end < speech_end
    ]
    return AudioTiming(duration, speech_start, speech_end, pauses)
