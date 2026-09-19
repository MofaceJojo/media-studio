# Grounded Visuals and Synced Subtitles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep generated visuals concretely aligned with narration while avoiding fragile faces/hands, and render phrase-level subtitles against measured narration audio.

**Architecture:** Generate one structured bilingual `VisualScenePlan` per narration, validate source quotes locally, verify all English translations in one strict temperature-zero LLM judge call, and derive both prompts from only the accepted facts followed by deterministic human-safety auditing. Build subtitle cues from real speech start/end and pauses detected by FFmpeg, using character weighting only as a logged fallback; share those cues between SRT export and final-video burn-in. Preserve and restore narration audio duration separately from rendered segment duration, and compute scene offsets from the actual post-production audio layout.

**Tech Stack:** Python 3.13, dataclasses, ffmpeg-python/libass, pytest, existing Streamlit and StandardPipeline.

## Global Constraints

- Default visuals do not show identifiable front-facing faces or detailed hands.
- Allowed human depictions are back views, distant silhouettes, over-the-shoulder views, occluded people, and archival/reference imagery.
- One structured visual plan supplies subject, location, action, outcome, and evidence to both image and video prompts; unrelated symbolic filler is rejected.
- Image and video prompts for one scene describe the same core subject and event.
- Subtitle display begins/ends at measured speech boundaries and phrase boundaries use measured audio pauses; proportional timing is only a logged fallback.
- Burned subtitles and exported SRT consume the same `SubtitleCue` list.
- A subtitle disappears when its narration audio ends; trailing visual silence carries no stale subtitle.
- No speech-recognition service, network dependency, face-restoration model, or external prompt database is added.
- The existing configured LLM may receive one batched translation-faithfulness judge call; malformed or negative verdicts never fail open.
- Existing user-edited narration and prompts remain authoritative.

---

## File Map

- Create `morpheus_video_studio/models/visual_scene_plan.py`: shared facts plus image/video prompts for one narration.
- Create `morpheus_video_studio/services/visual_scene_planner.py`: one structured LLM response for aligned scene facts and both prompt types.
- Create `morpheus_video_studio/utils/visual_prompt_policy.py`: shared safety, fact-coverage validation, and deterministic high-risk rewriting.
- Modify `morpheus_video_studio/prompts/image_generation.py`: require concrete narration grounding and the default safe-human policy.
- Modify `morpheus_video_studio/prompts/video_generation.py`: apply the same facts and safe-human policy to motion prompts.
- Modify `morpheus_video_studio/services/scene_draft_generator.py`: use the shared visual scene planner while preserving partial error reporting.
- Create `tests/test_visual_prompt_policy.py` and modify prompt/generator tests.
- Replace `morpheus_video_studio/utils/subtitle_export.py` with a pause-aware cue planner plus SRT serialization while preserving the legacy entry point.
- Create `morpheus_video_studio/utils/audio_timing.py`: FFmpeg silence detection and normalized backend timestamp handling.
- Modify `morpheus_video_studio/models/storyboard.py`: store measured narration audio duration and planned cues.
- Modify `morpheus_video_studio/services/persistence.py`: save/load audio duration and recover old tasks.
- Modify `morpheus_video_studio/services/frame_processor.py`: retain audio duration and remove static whole-scene subtitle text.
- Add `morpheus_video_studio/services/video/subtitles.py` and update the service facade: burn a supplied SRT into the final video using configured style.
- Modify `morpheus_video_studio/pipelines/standard.py`: build one global cue list, export it, and conditionally burn it into the final video.
- Modify/add subtitle, frame composition, video service, and pipeline tests.

---

### Task 1: Grounded and Human-Safe Visual Prompts

**Files:**
- Create: `morpheus_video_studio/utils/visual_prompt_policy.py`
- Create: `morpheus_video_studio/models/visual_scene_plan.py`
- Create: `morpheus_video_studio/services/visual_scene_planner.py`
- Modify: `morpheus_video_studio/prompts/image_generation.py`
- Modify: `morpheus_video_studio/prompts/video_generation.py`
- Modify: `morpheus_video_studio/services/scene_draft_generator.py`
- Create: `tests/test_visual_prompt_policy.py`
- Modify: `tests/test_content_recipes.py`
- Modify: `tests/test_scene_draft_generator.py`

**Interfaces:**
- Produces: `DEFAULT_SAFE_VISUAL_RULES: str`
- Produces: `build_visual_rules(extra_rules: str = "") -> str`
- Produces: `sanitize_visual_prompt(prompt: str) -> str`
- Produces: `VisualScenePlan(subject: str, location: str = "", action: str = "", outcome: str = "", evidence: str = "", image_prompt: str = "", video_prompt: str = "")`; only `subject` is mandatory and optional facts may not be invented.
- Produces: `async generate_visual_scene_plans(llm_service, narrations: list[str], visual_rules: str = "") -> list[VisualScenePlan]`
- Produces: one strict batched judge response per candidate plan set with exact fields `index`, `faithful_translation`, `english_only`, `no_added_details`, and `issues`.

- [ ] **Step 1: Write failing policy tests**

Test that the shared rules explicitly prefer objects/environments/reference imagery and back views/silhouettes, prohibit face/eye/hand close-ups and complex multi-person action, and require concrete narration evidence. Test deterministic rewriting of representative phrases such as `close-up portrait`, `expressive eyes`, `detailed hands`, and `two people embracing` while preserving safe object and environment terms. Test that a structured plan is rejected when its subject is blank or either prompt omits the shared subject; optional fact fields may be blank and blank fields cannot cause invented prompt content.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest -q tests/test_visual_prompt_policy.py`

Expected: fail because `visual_prompt_policy` does not exist.

- [ ] **Step 3: Implement the minimal shared policy**

Define one concise English rule block, structured plan dataclass, fact-coverage validator, and a case-insensitive replacement table. Require the subject and validate only non-empty optional facts. Rewriting must replace risky compositions with `distant back-view silhouette`, `face fully turned away`, `hands outside the frame`, or an object/environment alternative; it must not delete the complete prompt or invent a new named entity.

- [ ] **Step 4: Run GREEN**

Run: `.venv/bin/python -m pytest -q tests/test_visual_prompt_policy.py`

Expected: all policy tests pass.

- [ ] **Step 5: Write failing integration tests**

Mock one LLM plan response and one judge response for all narrations. Assert strict JSON count/index/field validation at both stages, source facts are exact narration substrings, all judge booleans are true with empty issues, safe-human sanitization, and conversion into aligned `SceneDraft.image_prompt` / `video_prompt`. Assert embellished or non-English translations, malformed/empty/wrong-count/extra-field judge responses retry and finally report a visual-plan error without corrupting narration.

- [ ] **Step 6: Run integration RED**

Run: `.venv/bin/python -m pytest -q tests/test_content_recipes.py tests/test_scene_draft_generator.py tests/test_visual_prompt_policy.py`

Expected: new video-rule forwarding and sanitizer assertions fail.

- [ ] **Step 7: Wire the policy into both prompt paths**

Build one prompt that requests bilingual fact pairs per narration and validates source quotes locally. Send the complete candidate plan set through one batched `temperature=0` judge with exact schema; require `faithful_translation`, `english_only`, and `no_added_details` to be true and `issues` empty for every contiguous index. Invalid or negative verdicts re-enter the existing whole-plan retry and never fail open. Assemble both prompts in Python only from accepted English facts, sanitize them, and use the planner from `scene_draft_generator`; keep legacy standalone generators for older callers, but prepend the same safety rules and remove their symbolic-filler instructions.

- [ ] **Step 8: Verify and commit**

Run: `.venv/bin/python -m pytest -q tests/test_content_recipes.py tests/test_scene_draft_generator.py tests/test_visual_prompt_policy.py tests/test_scene_draft_pipeline.py`

Expected: all focused tests pass.

Commit: `feat: ground visual prompts and avoid fragile people`

---

### Task 2: Phrase-Level Subtitle Cue Planning

**Files:**
- Modify: `morpheus_video_studio/utils/subtitle_export.py`
- Create: `morpheus_video_studio/utils/audio_timing.py`
- Modify: `morpheus_video_studio/models/storyboard.py`
- Modify: `morpheus_video_studio/services/persistence.py`
- Modify: `tests/test_subtitle_export.py`

**Interfaces:**
- Produces: `SubtitleCue(text: str, start: float, end: float)`
- Produces: `AudioTiming(duration: float, speech_start: float, speech_end: float, pauses: list[tuple[float, float]])`
- Produces: `detect_audio_timing(audio_path: str, *, min_silence: float = 0.12) -> AudioTiming`
- Produces: `plan_segment_cues(text: str, timing: AudioTiming, *, max_chars: int = 18) -> list[SubtitleCue]`
- Produces: `TimelineSegment(text: str, audio_timing: AudioTiming, timeline_duration: float)`
- Produces: `build_global_cues(segments: list[TimelineSegment], *, max_chars: int = 18) -> list[SubtitleCue]`
- Produces: `export_srt_cues(cues: list[SubtitleCue], output_path: str) -> str`
- Preserves: `export_srt(segments, output_path) -> str`
- Adds: `StoryboardFrame.audio_duration: float`; cues remain derived and are not persisted on the frame.

- [ ] **Step 1: Write failing split and timing tests**

Cover Chinese punctuation, overlong unpunctuated text, empty text, zero duration, and mixed Latin/Chinese text. Assert normalized cue text reconstructs the original non-whitespace content and cues are ordered and non-overlapping. With synthetic leading/trailing silence, assert the first cue starts at `speech_start` and the final cue ends at `speech_end`; with middle pause candidates, assert sentence boundaries land on pause midpoints.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest -q tests/test_subtitle_export.py`

Expected: fail because the cue and audio-timing APIs do not exist.

- [ ] **Step 3: Implement punctuation-weighted cue planning**

Split at `，、；：。！？,.!?;:` and enforce `max_chars` without dropping punctuation. Parse FFmpeg `silencedetect` output into `speech_start`, `speech_end`, and middle pause intervals. Match ordered phrase boundaries to ordered pause midpoints by minimum distance from their proportional target. Only unmatched boundaries use visible character count plus pause weights (comma/colon `0.35`, semicolon `0.45`, sentence ending `0.7`) within the measured speech interval. Return no cues for empty text or a missing/non-positive speech interval and log when fallback interpolation is used.

- [ ] **Step 4: Add failing global timeline and compatibility tests**

Assert later scenes begin after each preceding `timeline_duration`, while each local cue stays within `speech_start`/`speech_end`, leaving leading and trailing gaps cue-free. Assert `export_srt_cues` serializes exact cue times and legacy `export_srt` delegates to the new planner using a zero-leading-silence compatibility timing.

- [ ] **Step 5: Implement global planning and serialization**

Offset each local cue by the global cursor, advance the cursor by `timeline_duration`, and serialize the supplied cue objects. Add `audio_duration` to the model. Extend persistence to save/load it; when loading an old record or reusing an existing segment, probe the audio file before falling back to segment duration. Add round-trip and legacy recovery tests.

- [ ] **Step 6: Verify and commit**

Run: `.venv/bin/python -m pytest -q tests/test_subtitle_export.py tests/test_storyboard_models.py 2>/dev/null || .venv/bin/python -m pytest -q tests/test_subtitle_export.py`

Expected: all discovered focused tests pass.

Commit: `feat: plan phrase-level subtitle cues from audio`

---

### Task 3: Shared Dynamic Burn-In and Pipeline Integration

**Files:**
- Create: `morpheus_video_studio/services/video/subtitles.py`
- Modify: `morpheus_video_studio/services/video/service.py`
- Modify: `morpheus_video_studio/services/frame_processor.py`
- Modify: `morpheus_video_studio/pipelines/standard.py`
- Create: `tests/test_video_subtitles.py`
- Modify: `tests/test_subtitle_export.py`
- Modify: `tests/test_subtitle_config.py`

**Interfaces:**
- Produces: `SubtitleMixin.burn_subtitles(video: str, subtitle_file: str, output: str, *, font: str, position: str, color: str, size: int, stroke_color: str, stroke_width: float) -> str`
- Consumes: `build_global_cues([TimelineSegment(...)])` using the actual concat mode's audio layout.
- Consumes: `export_srt_cues(cues, path)` for both upload and burn-in.

- [ ] **Step 1: Write failing frame/pipeline behavior tests**

Assert TTS stores `audio_duration` before media generation can change `duration`; reused segments re-probe their audio; HTML composition receives an empty `text` value instead of the whole narration; ordinary concat sets each `timeline_duration` to final segment duration, while sequential-audio xfade uses audio duration plus its explicit gap; subtitle-disabled mode neither calls burn-in nor leaves template text; subtitle-enabled mode exports then burns the same SRT path.

- [ ] **Step 2: Run RED**

Run: `.venv/bin/python -m pytest -q tests/test_subtitle_config.py tests/test_subtitle_export.py`

Expected: the new static-text removal and post-production assertions fail.

- [ ] **Step 3: Preserve audio timing and remove static subtitles**

Set both `frame.audio_duration` and the initial `frame.duration` after probing TTS. Always pass an empty template text value from `_compose_frame_html`; dynamic subtitles will be added only after final concatenation. Keep titles and other template metadata unchanged.

- [ ] **Step 4: Write failing ffmpeg burn-in tests**

Create a tiny synthetic color video and SRT fixture. Assert `burn_subtitles` produces a playable output of equal duration with an audio stream preserved when present. Unit-test style mapping for bottom/center/top alignment, ASS color conversion, and safe escaping of subtitle paths.

- [ ] **Step 5: Run burn-in RED**

Run: `.venv/bin/python -m pytest -q tests/test_video_subtitles.py`

Expected: fail because `SubtitleMixin` does not exist.

- [ ] **Step 6: Implement final-video subtitle burn-in**

Use ffmpeg's `subtitles` filter with `force_style` derived from existing configuration, encode video as H.264/yuv420p, copy or encode audio to AAC as required, write to a temporary sibling path, and atomically replace the requested final path only after ffmpeg succeeds. Preserve the standalone SRT.

- [ ] **Step 7: Integrate the shared cue list**

After concatenation, construct `TimelineSegment` values from the actual concat mode: ordinary concat advances by final segment duration; current xfade sequential narration advances by raw audio duration plus explicit narration gap. Detect speech boundaries and pauses from each audio file, build cues, export beside the final output, and call `burn_subtitles` only when `subtitle_enabled` is true. When a user-specified output path exists, perform burn-in before the final copy so both paths represent the same rendered video. Keep SRT export available when subtitles are enabled; do not emit a misleading static subtitle when disabled. Style mapping must use the existing `top/center/bottom` names.

- [ ] **Step 8: Verify and commit**

Run: `.venv/bin/python -m pytest -q tests/test_video_subtitles.py tests/test_subtitle_export.py tests/test_subtitle_config.py tests/test_video_service_xfade.py`

Expected: all focused tests pass.

Commit: `fix: synchronize burned subtitles with narration`

---

### Task 4: Regression and Browser Smoke Verification

**Files:**
- Modify only if a regression test exposes a defect.

**Interfaces:**
- Verifies Tasks 1–3 together; produces no new public API.

- [ ] **Step 1: Run the complete automated suite**

Run: `.venv/bin/python -m pytest -q`

Expected: all tests pass with no failures.

- [ ] **Step 2: Run deterministic subtitle media smoke test**

Generate a short local synthetic video with a two-sentence cue file, burn it, probe duration/audio/video streams, and inspect representative frames from before and after the cue boundary to prove text changes and disappears by the final cue end.

- [ ] **Step 3: Start the latest worktree on port 18501 and smoke-test Quick Create**

Open `/Video_Workshop`, generate or load a scene draft, and confirm the visible image/video prompts contain concrete scene facts and the no-face/no-hands strategy. Confirm configuration and history remain reachable from the persistent left drawer.

- [ ] **Step 4: Request whole-branch review and resolve findings**

Review the complete branch diff for spec compliance, subtitle drift risks, ffmpeg portability, and prompt-regression risks. Apply all Critical/Important fixes and re-run their covering tests.

- [ ] **Step 5: Final verification commit**

Run: `.venv/bin/python -m pytest -q`

Expected: all tests pass.

Commit documentation/test evidence as `docs: record grounded visual and subtitle verification` if evidence files changed.
