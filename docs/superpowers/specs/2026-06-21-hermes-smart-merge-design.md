# Hermes Smart Merge Design

## Summary

Add a natural-language Hermes entrypoint for Media Studio that can take a user request such as “用 moface media studio 把这个文件夹里的素材拼成一个顺滑混剪视频” and turn it into a local smart-merge job.

The first version should be intentionally narrow:

- Input: local image/video assets plus a short natural-language request
- Output: one merged video file
- Style: default to a stable “顺滑混剪” strategy
- Execution: Hermes skill calls a local Python CLI, and the CLI reuses Media Studio’s existing merge/composition services

This is not a new video generation system. It is a thin natural-language control layer on top of the existing local Media Studio capabilities.

## Goals

- Let Hermes users trigger a local Media Studio merge job with one natural-language instruction
- Avoid requiring the user to manually specify fps, ratio, clip duration, transitions, or output path
- Reuse existing Media Studio merge/composition logic rather than building a second ffmpeg stack
- Keep V1 deterministic enough that failures are explainable and logs are inspectable

## Non-Goals

- Do not support PDF-to-video in this feature
- Do not support digital human, TTS generation, or OmniVoice in this feature
- Do not make Hermes drive the Streamlit UI
- Do not expose a full parameter surface in V1
- Do not attempt semantic shot matching against narration text in V1

## User Experience

### Example requests

- “用 moface media studio 把桌面这个水浒素材文件夹拼成一个顺滑混剪视频”
- “帮我把 Downloads 里的旅行图片和视频自动拼成一个成片”
- “用 media studio 智能拼接这个文件夹里的素材，输出一个可以直接看的视频”

### Expected V1 behavior

Hermes should:

1. recognize the request as a Media Studio smart-merge task
2. identify one local folder or a short list of local files
3. invoke a local CLI in this repo
4. let the CLI inspect assets and choose sane defaults
5. return the final output path and a short summary of what it did

If no local path is present, Hermes should ask for exactly one folder or a set of files.

## Approaches Considered

### Option A: Hermes drives Streamlit directly

Pros:

- no new backend entrypoint

Cons:

- fragile against UI changes
- harder to debug
- poor fit for automation and future reuse

### Option B: Hermes emits raw ffmpeg commands

Pros:

- fast to prototype

Cons:

- duplicates Media Studio logic
- creates a second behavior surface outside the app
- makes future tuning diverge

### Option C: Hermes skill -> local CLI -> Media Studio services

Pros:

- reuses existing code
- stable integration boundary
- works for both Hermes and future shell automation
- easier to test and log

Cons:

- requires a thin adapter layer

### Recommendation

Choose Option C.

## System Design

### 1. Hermes skill

Add a Hermes/Codex skill whose only job is to:

- detect natural-language requests that mean “smart merge local assets with Media Studio”
- extract the local asset path if present
- call the local CLI with the user request and the resolved path
- report output path and failure messages back in a concise format

The skill should not encode merge logic itself.

### 2. Local CLI

Add a small Python entrypoint at:

- `tools/media_studio_agent.py`

Suggested interface:

```bash
python tools/media_studio_agent.py smart-merge \
  --request "用 moface media studio 把这个文件夹拼成一个顺滑混剪视频" \
  --input "/absolute/path/to/assets"
```

Responsibilities:

- validate the input path
- enumerate supported media files
- infer a merge plan
- call existing Media Studio services
- print machine-readable and human-readable result data

### 3. Smart merge adapter

Add a small adapter layer inside the repo, separate from the CLI, for example:

- `morpheus_video_studio/services/smart_merge_agent.py`

Responsibilities:

- collect candidate files
- classify images vs videos
- choose default layout
- choose default clip duration for still images
- choose default transitions and motion behavior
- call existing merge/composition service functions

This keeps business logic in Python modules, not in CLI glue.

## Reuse Plan

V1 should reuse existing capabilities where possible:

- `web/pipelines/video_merge.py`
- `morpheus_video_studio/services/stock_publish_tools.py`
- `morpheus_video_studio/services/video.py`

The new adapter should call the underlying services directly rather than importing Streamlit pipeline UI code.

If the current service boundary is too UI-shaped, the refactor should be:

1. extract pure merge logic into a shared service function
2. have both Streamlit and the new CLI call that function

Do not leave duplicated merge logic in both places.

## Default Smart Strategy

V1 should hardcode one safe mode: `smooth_mix`.

Suggested defaults:

- layout:
  - prefer `16:9` if most assets are landscape
  - prefer `9:16` if most assets are portrait
  - fallback to `16:9`
- fps: `30`
- image clip duration: adaptive in the `3.5s - 5.5s` range
- transitions: light transitions only, e.g. `fade`, `dissolve`, `wipeleft`
- image motion: `gentle` or `float`
- output location: a dedicated results folder under the repo `output/` tree
- output name: timestamp + sanitized task label

The adapter may later support multiple styles, but V1 should expose only one.

## Input Resolution Rules

V1 input resolution should be explicit and conservative:

- if `--input` points to a directory, scan supported files recursively
- if `--input` points to a file, treat it as a single-item list
- if multiple files are passed later, preserve the provided order
- if a directory is scanned, sort files by filename for determinism

Supported V1 asset types:

- images: `.jpg`, `.jpeg`, `.png`, `.webp`
- videos: `.mp4`, `.mov`, `.m4v`

Unsupported files should be ignored and counted in the summary.

## Failure Handling

The CLI should fail fast with clear messages for:

- input path missing
- no supported media files found
- ffmpeg unavailable
- merge service exception

The returned message should include:

- what input path was used
- how many supported assets were found
- where logs or outputs were written

## Logging and Outputs

Each run should create a dedicated task directory under `output/`, containing:

- final merged video
- a small JSON summary
- a plain-text log or plan summary

Suggested metadata fields:

- request
- input_path
- asset_count
- image_count
- video_count
- chosen_layout
- chosen_fps
- output_path
- status
- error

## Testing

### Unit tests

- input scanning and file filtering
- layout inference
- deterministic output naming
- empty-folder and unsupported-file handling

### Integration tests

- mixed folder of images and videos produces one output file
- image-only folder produces one output file
- bad path returns clear failure

### Manual test

Run Hermes with a natural-language request pointing at a local folder and verify:

- Hermes chooses the skill
- CLI runs locally
- Media Studio produces a merged video
- final response includes the output path

## Rollout Plan

### Phase 1

- add shared smart-merge service
- add local CLI
- test CLI directly

### Phase 2

- add Hermes skill wrapper
- validate natural-language invocation from Hermes

### Phase 3

- polish prompts and failure messages
- optionally add one or two style presets later

## Open Questions Resolved For V1

- Should users set detailed parameters in natural language? No.
- Should Hermes control the web UI? No.
- Should this reuse Media Studio internals rather than raw ffmpeg commands? Yes.
- Should the first style be conservative and stable? Yes.

## Implementation Boundary

The implementation should stop after “smart merge local assets into one video via Hermes natural language”.

Anything beyond that, including:

- semantic matching to narration
- automatic voiceover creation
- PDF ingestion
- digital human output
- multi-style creative presets

belongs to later features, not this V1.
