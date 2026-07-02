# Media Studio Platform Plan

## Goal

Build the project into a content-first media studio:

- Content input becomes a reusable library
- Audio generation is a first-class workflow
- Video generation is a first-class workflow
- Digital human generation remains a first-class workflow
- Generated assets can flow back into reusable libraries

## Top-Level Modules

The platform should evolve toward five primary modules:

1. Content Library
2. Audio Workshop
3. Video Workshop
4. Digital Human
5. Asset Library

## Module Boundaries

### 1. Content Library

Purpose:
- Store reusable source material instead of treating every input as a one-off task

Typical inputs:
- PDF
- Word
- PPT
- TXT / Markdown
- Script notes
- Travel routes
- Quotes / aphorisms

Core fields:
- `content_id`
- `title`
- `content_type`
- `source_path`
- `extracted_text`
- `summary`
- `tags`
- `status`
- `created_at`
- `updated_at`

### 2. Audio Workshop

Purpose:
- Turn content into reusable audio assets

Outputs:
- Narration
- Multi-voice variants
- OmniVoice voice styles
- Reusable speech assets

Recommended engines:
- OmniVoice as the preferred premium/local TTS engine
- Edge TTS as fallback
- ComfyUI TTS as optional advanced mode

### 3. Video Workshop

Purpose:
- Turn content or scripts into finished videos

Main workflows:
- Document-to-video
- AI visual video
- Stock-assisted video
- Asset-assisted video

Important rule:
- Document-to-video should become the primary workflow for this product direction
- Generic stock search should be secondary, not the default center of gravity

### 4. Digital Human

Purpose:
- Keep digital human generation as a dedicated, first-class production mode

Why it stays separate:
- Different input structure
- Different asset dependencies
- Different output expectations

Suggested inputs:
- Character asset
- Script or content item
- Audio asset or generated speech
- Optional goods / presentation materials

### 5. Asset Library

Purpose:
- Store and reuse generated or imported media assets

Asset groups:
- Audio assets
- Video assets
- Image assets
- Digital human assets
- Local IP / licensed footage assets

## Data Model

Recommended core entities:

- `ContentItem`
- `AudioAsset`
- `VideoAsset`
- `MediaAsset`
- `GenerationJob`

Relationships:
- One `ContentItem` can produce many `AudioAsset`
- One `ContentItem` can produce many `VideoAsset`
- One `VideoAsset` can reference one or more `AudioAsset`
- `GenerationJob` stores the execution history and parameters

## Recommended Product Direction

### Primary Mainline

`Content Library -> Audio Workshop / Video Workshop / Digital Human`

This should be the default product story.

### Secondary Mainline

`Standalone generation tools`

These remain useful, but should no longer define the whole product:
- Generic topic-to-video
- Stock materials search
- One-off AI image/video generation

## Current Project Mapping

Existing capabilities already provide a base:

- `web/components/content_input.py`
  - already supports document upload and extracted text input
- `morpheus_video_studio/pipelines/book_pdf.py`
  - already provides a document-to-video pipeline base
- `morpheus_video_studio/services/tts_service.py`
  - already supports `local`, `omnivoice`, and `comfyui`
- `web/pipelines/digital_human.py`
  - already provides a dedicated digital human workflow
- `morpheus_video_studio/services/persistence.py`
  - already stores task artifacts and can be extended toward asset persistence

## V1 Implementation Priorities

### Phase 1: Library Foundation

- Add a real Content Library page
- Persist uploaded documents as reusable content items
- Add an Audio Workshop page
- Save generated audio into a reusable audio library

### Phase 2: Mainline Correction

- Promote document-to-video to a first-class homepage workflow
- Stop hardwiring document interpretation flows to generic stock-first behavior
- Add content-type presets:
  - quotes / aphorisms
  - travel route
  - book summary

### Phase 3: Reuse Loop

- Let Video Workshop select from existing audio assets
- Let Digital Human select from existing audio or content assets
- Let generated outputs flow back into Asset Library

## Explicit Non-Goals

To avoid repeating the current drift, the platform should not try to hide every capability behind one black-box button.

Avoid:
- auto-switching silently between too many unrelated pipelines
- treating AI-generated visuals, public stock search, and IP-library retrieval as the same user promise
- expanding the default quick-create flow into an opaque “do everything” path

## Guiding Product Principle

This platform should behave like a media workspace, not just a task runner.

The user should be able to:
- bring in content once
- generate many assets from it
- reuse those assets later
- understand which mode produced which result
