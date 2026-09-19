# Task 3 Report: Shared Dynamic Burn-In and Pipeline Integration

## Status

Implemented with strict RED -> GREEN cycles from baseline `9c0f564`.

## Delivered behavior

- TTS probing now stores both the immutable narration `audio_duration` and the
  initial frame `duration`.
- Reused frame segments re-probe their existing `audio_path` while preserving
  the final segment duration separately.
- HTML frame composition always receives an empty `text` value, so narration is
  never rendered as a full-scene static subtitle.
- Added `SubtitleMixin.burn_subtitles` and composed it into `VideoService`.
  - Uses FFmpeg's `subtitles`/libass filter when available.
  - Falls back to Pillow-rendered transparent cue images and timed FFmpeg
    overlays when the installed FFmpeg lacks libass.
  - Both paths encode H.264/yuv420p, preserve audio as AAC, write a sibling
    temporary file, and atomically replace the requested output only on success.
- Subtitle styling maps `bottom`, `center`, and `top` to ASS alignment values
  `2`, `5`, and `8`, converts CSS colors to ASS colors, and safely escapes SRT
  paths through ffmpeg-python's filter graph compiler.
- Standard post-production now uses `detect_audio_timing`, `TimelineSegment`,
  `build_global_cues`, and `export_srt_cues`.
  - Ordinary concat advances by each final segment duration.
  - Sequential-audio xfade advances by detected raw audio duration plus the
    explicit inter-segment audio gap.
  - The exact cue list exported to SRT is passed to burn-in.
  - Burn-in completes on the internal final video before any user-output copy.
  - Subtitle-disabled mode exports nothing and burns nothing.

## TDD evidence

Initial frame/pipeline RED:

```text
7 failed, 17 passed
```

Burn-in RED:

```text
ModuleNotFoundError: No module named
'morpheus_video_studio.services.video.subtitles'
```

The first Pillow fallback run exposed an unbounded overlay caused by a looping
PNG input. The hanging test processes were stopped, `overlay shortest=1` was
added, and the same real-media test completed in 0.52 seconds.

## Verification

```text
.venv/bin/python -m pytest -q \
  tests/test_video_subtitles.py tests/test_subtitle_export.py \
  tests/test_subtitle_config.py tests/test_video_service_xfade.py
32 passed in 2.60s

.venv/bin/python -m pytest -q
234 passed, 12 warnings in 10.21s
```

The 12 warnings are existing Pydantic v2 deprecation warnings from API schema
imports. Additional checks:

- Real no-libass Pillow/overlay test: 6 passed in 0.52s, including cue boundary
  frame changes, equal duration, preserved audio, H.264, and yuv420p.
- `compileall`: passed.
- `git diff --check`: passed.
- Ruff on new subtitle/test files: passed.
- Ruff across all touched files, excluding pre-existing import-order,
  placeholder-free f-string, and unused-symbol findings: passed.

## Concerns

- The Pillow fallback creates one transparent PNG file per cue, then encodes all
  files through one concat-demuxer input into one lossless alpha overlay video.
  FFmpeg graph/input count is constant, but very long videos can still use
  meaningful temporary disk space while those PNGs exist.
- Font rendering depends on locally available fonts. It tries the configured
  font first, then common macOS CJK/Arial fonts, then DejaVu/default Pillow font.
- The libass path is unit-tested here, but this machine's Homebrew FFmpeg lacks
  the `subtitles` filter; the real-media integration therefore exercises the
  production Pillow fallback on this platform.

## Review fixes

The follow-up review reported two Important and two Minor findings. All four
were reproduced with failing tests before implementation:

```text
5 failed, 6 passed
```

Corrections:

- `transition_audio_delay` is normalized exactly once with
  `max(0.0, float(...))`; the same value now drives concat and the xfade cue
  cursor. A negative-delay regression confirms the second cue starts after the
  full first audio duration rather than early.
- The no-libass fallback no longer adds one FFmpeg input/overlay per cue. Cue
  PNGs and blank gaps are described by one concat manifest, encoded as one
  qtrle/ARGB overlay video, then composited with one overlay operation. A 501-cue
  test proves every FFmpeg command has at most two inputs and the composite
  graph contains exactly one overlay.
- Pillow rendering wraps at character boundaries and progressively downscales
  the configured font until text fits. A long full-width CJK regression checks
  the rendered alpha pixels remain inside the 5% horizontal margins.
- Audio silence detection runs through `asyncio.to_thread` with a four-task
  semaphore and `asyncio.gather`; the pipeline test records both narration files
  crossing that thread boundary.
- An additional manifest-boundary RED/GREEN regression ensures cues after the
  source video cannot extend the alpha timeline past the video duration.

Fresh post-review verification:

```text
.venv/bin/python -m pytest -q \
  tests/test_video_subtitles.py tests/test_subtitle_export.py \
  tests/test_subtitle_config.py tests/test_video_service_xfade.py
36 passed in 2.79s

.venv/bin/python -m pytest -q
238 passed, 12 warnings in 9.90s
```

The real no-libass Mac fallback remains covered by the playable-video test,
including timed frame changes, audio preservation, duration, H.264, and yuv420p.

## Final review fixes

The final review reported one Important and one Minor finding. New tests first
reproduced all affected paths:

```text
5 failed
```

Corrections:

- The Pillow fallback now converts the probed video duration to `float`, catches
  probe exceptions, and requires a finite value greater than zero before it
  creates a manifest, runs either FFmpeg command, or atomically replaces output.
  Regressions cover zero, NaN, and a raised probe failure; each verifies no
  command, no replacement, and preservation of an existing output file.
- The single-overlay filter now uses `eof_action=pass` with `shortest=0`, so an
  unexpectedly early alpha-overlay EOF cannot truncate the validated source
  video. Manifest cue bounds remain clamped to the validated source duration.
- Text wrapping now bounds work for extreme inputs, downscales to the configured
  minimum, then deterministically truncates whole lines and adds an ellipsis.
  A 6,000-character cue test verifies all non-transparent pixels remain inside
  both horizontal and vertical safe margins.
- A separate 18-character regression confirms ordinary cue text remains complete
  and is not ellipsized. The current Mac playable fallback test remains green.

Fresh final-review verification:

```text
.venv/bin/python -m pytest -q \
  tests/test_video_subtitles.py tests/test_subtitle_export.py \
  tests/test_subtitle_config.py tests/test_video_service_xfade.py
41 passed in 2.97s

.venv/bin/python -m pytest -q
243 passed, 12 warnings in 9.99s
```
