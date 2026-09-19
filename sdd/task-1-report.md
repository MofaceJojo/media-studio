# Task 1 report — Grounded and Human-Safe Visual Prompts

## Changes

- Added the shared safe-visual policy, deterministic case-insensitive rewrites, and rule composition helper.
- Added `VisualScenePlan` with required-subject and non-empty fact coverage checks for both prompts.
- Added a single structured visual planner with strict JSON root/count/index/field validation, sanitization, and three retries.
- Changed scene-draft generation to consume aligned planner output atomically; a planner error preserves narration and leaves both visual prompts blank.
- Applied the same shared safety block to legacy image and video prompt builders, forwarded video visual rules, and removed symbolic-metaphor generation guidance.

## RED evidence

Command:

```sh
.venv/bin/python -m pytest -q tests/test_visual_prompt_policy.py
```

Result before implementation: collection failed with `ModuleNotFoundError: No module named 'morpheus_video_studio.models.visual_scene_plan'` (the required policy/plan modules did not exist).

Integration RED command:

```sh
.venv/bin/python -m pytest -q tests/test_content_recipes.py tests/test_scene_draft_generator.py tests/test_visual_prompt_policy.py
```

Result before planner implementation: collection failed with `ModuleNotFoundError: No module named 'morpheus_video_studio.services.visual_scene_planner'`.

## GREEN verification

```sh
.venv/bin/python -m pytest -q tests/test_visual_prompt_policy.py
# 4 passed

.venv/bin/python -m pytest -q tests/test_content_recipes.py tests/test_scene_draft_generator.py tests/test_visual_prompt_policy.py
# 27 passed

.venv/bin/python -m pytest -q tests/test_content_recipes.py tests/test_scene_draft_generator.py tests/test_visual_prompt_policy.py tests/test_scene_draft_pipeline.py
# 46 passed

git diff --check
.venv/bin/python -m compileall -q morpheus_video_studio
# both passed
```

## Self-review

- Strict JSON permits only `plans` at the root and exactly the specified fields per contiguous, 1-based item.
- All supplied facts are required in both prompts; blank optional facts are ignored and therefore cannot introduce invented content.
- The sanitizer replaces only risky composition phrases and preserves other scene/object/environment text.
- The three pre-existing untracked task reports were left untouched.

## Commit

`feat: ground visual prompts and avoid fragile people`

## Review fix: fact grounding and expanded human safety

### Changes

- `VisualScenePlan` now validates every non-empty subject/location/action/outcome/evidence value as an exact substring of its matching original narration before either prompt is checked. Facts therefore remain in the narration's language and cannot be invented by the planner.
- The planner rejects non-list, non-string, and blank narrations before calling the LLM.
- Default rules now forbid identifiable/front-facing faces, eyes, and visible or detailed hands/fingers, and require occluded distant back views or silhouettes whenever people appear.
- The sanitizer now handles front-facing/front-view, portrait, face, eye, hand, and finger variants case-insensitively while retaining surrounding objects and environments.
- Legacy image and video prompt generators now sanitize every returned prompt.

### RED evidence

```sh
.venv/bin/python -m pytest -q tests/test_visual_prompt_policy.py tests/test_scene_draft_generator.py
```

Before the fix: `8 failed, 13 passed`. Failures showed missing stricter rule wording, unsanitized front-view/portrait/visible-hand output from both legacy generators, invented `location`/`evidence` accepted by the planner, and `None`/numeric narrations reaching the LLM.

### GREEN verification

```sh
.venv/bin/python -m pytest -q tests/test_visual_prompt_policy.py tests/test_scene_draft_generator.py
# 21 passed in 0.12s

.venv/bin/python -m pytest -q tests/test_content_recipes.py tests/test_scene_draft_generator.py tests/test_visual_prompt_policy.py tests/test_scene_draft_pipeline.py
# 54 passed in 0.36s

git diff --check
.venv/bin/python -m compileall -q morpheus_video_studio
# both passed
```

### Self-review

- Fact-to-narration verification is deterministic substring matching; no new LLM judge was added.
- Validation order is narration facts first, then sanitized prompt coverage.
- The sanitizer only substitutes unsafe human composition phrases, preserving neighboring scene/object/environment text.
- Unrelated untracked task reports remain untouched.

### Concerns

None.

### Fix commit

`fix: judge visual fact translations`

### Fix commit

`fix: build visual prompts from grounded facts`

## Review fix: faithful translation judge

### Changes

- Added one batched, same-service translation-fidelity judge after all plans are parsed and before they are accepted.
- Judge input contains each original narration plus every fact's `source` and `english` values. It runs with `temperature=0` and has no new dependency or network client.
- Verdict parsing is strict: exact root/count/index/fields, boolean types, and issue-array types are required. All three booleans must be true and `issues` empty; blank, malformed, incomplete, extra-field, or rejecting verdicts fail closed.
- A plan or judge failure retries the complete planning cycle under the existing three-attempt limit.

### RED evidence

```sh
.venv/bin/python -m pytest -q tests/test_scene_draft_generator.py
```

Before the judge implementation: `7 failed, 14 passed`. The failures showed no temperature-0 judge call, embellished Eiffel/Paris translations accepted without a fresh planning attempt, and empty/malformed/wrong-count/extra-field/non-English verdicts failing open.

### GREEN verification

```sh
.venv/bin/python -m pytest -q tests/test_scene_draft_generator.py
# 21 passed in 0.13s

.venv/bin/python -m pytest -q tests/test_content_recipes.py tests/test_scene_draft_generator.py tests/test_visual_prompt_policy.py tests/test_scene_draft_pipeline.py
# 63 passed in 0.41s

git diff --check
.venv/bin/python -m compileall -q morpheus_video_studio
# both passed
```

### Self-review

- Exactly one judge request is made per parsable plan set, after parsing and before acceptance; judge failure never returns that candidate.
- The judge schema rejects empty, malformed, wrong-count, and extra-field responses and requires `issues=[]` with all acceptance booleans true.
- Rejection retries the complete planner request, preventing multiple accepted candidate sets.
- Existing bilingual fact pairs and Python-only prompt assembly remain unchanged.

### Concerns

None.

### Fix commit

`fix: validate grounded visual plan facts`

## Review fix: bilingual fact pairs and deterministic prompts

### Changes

- Replaced free-form LLM `image_prompt` / `video_prompt` fields with strict bilingual fact pairs. Each plan now contains only `subject`, `location`, `action`, `outcome`, and `evidence`, each with `source` and `english`.
- `source` must be an exact non-empty narration substring whenever a fact is present; optional pairs must be blank together. The subject pair is required.
- Python now deterministically builds the final English image/video prompts from non-empty English translations plus fixed grounded composition, documentary-style, safe-human, and video-motion clauses. Free-form prompt fields are strict-schema errors.
- Removed the image template's small/medium-face and conditional back-view language in favor of an absolute identifiable/front-facing face, eye, hand, and finger prohibition.
- Extended sanitization to ordinary person nouns while preserving surrounding object/environment text.

### RED evidence

```sh
.venv/bin/python -m pytest -q tests/test_visual_prompt_policy.py tests/test_scene_draft_generator.py
```

Expected and observed RED: collection failed with `ImportError: cannot import name 'VisualFact'`, proving the requested bilingual fact-pair API did not yet exist. A subsequent regression RED caught non-idempotent sanitization of the fixed `face fully turned away` clause (`fully turned away fully` present).

### GREEN verification

```sh
.venv/bin/python -m pytest -q tests/test_visual_prompt_policy.py tests/test_scene_draft_generator.py
# 24 passed in 0.12s

.venv/bin/python -m pytest -q tests/test_content_recipes.py tests/test_scene_draft_generator.py tests/test_visual_prompt_policy.py tests/test_scene_draft_pipeline.py
# 57 passed in 0.37s

git diff --check
.venv/bin/python -m compileall -q morpheus_video_studio
# both passed
```

### Self-review

- Strict JSON accepts only the fact-pair schema, exact plan fields, contiguous indexes, and matching counts.
- Final `SceneDraft` prompts are English strings assembled in Python; LLM-supplied prose such as Paris/rain details is rejected as an extra field.
- Fact validation remains deterministic and requires no LLM judge or network call.
- The ordinary-person sanitizer emits an explicit distant back-view silhouette with face turned away and hands outside frame, while retaining safe scene terms.
- Unrelated untracked task reports remain untouched.

### Concerns

None.
