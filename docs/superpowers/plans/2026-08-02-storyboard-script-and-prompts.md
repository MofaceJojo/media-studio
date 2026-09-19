# Storyboard Script and Prompts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate, display, edit, and reuse a scene-aligned trio of film narration, image prompt, and video prompt in Quick Create.

**Architecture:** Add a small, serializable `SceneDraft` model and a staged draft-generation service that reuses the existing narration/image/video generators. The Streamlit component stores the scenes as dictionaries in session state and renders one editable card per scene. The standard pipeline accepts those dictionaries as optional overrides, validates alignment, and selects image or video prompts according to the active template without regenerating user-edited values.

**Tech Stack:** Python 3, dataclasses, Streamlit, pytest, existing Morpheus LLM prompt generators and `StandardPipeline`.

## Global Constraints

- Each scene displays narration, image prompt, and video prompt separately under one scene number.
- Narration is expanded by default; visual prompts are collapsed by default.
- Film/TV ranking narration names concrete characters, plot events, conflict, and selection reason instead of abstract emotional prose.
- Existing user-edited prompts are never regenerated or overwritten during final video generation.
- Prompt list length must equal narration list length; mismatches fail explicitly rather than silently shifting scenes.
- A failed image- or video-prompt stage preserves narration and the other successful prompt type.
- Legacy plain-text narration drafts remain supported.
- Online factual verification is out of scope.

---

## File Map

- Create `morpheus_video_studio/models/scene_draft.py`: typed scene-draft value object and dictionary conversion.
- Create `morpheus_video_studio/services/scene_draft_generator.py`: staged narration, image-prompt, and video-prompt generation with partial-result preservation.
- Modify `morpheus_video_studio/prompts/content_recipes.py`: strengthen the ranking recipe toward plot-specific film/TV explanation.
- Modify `morpheus_video_studio/utils/content_generators.py`: reject structurally valid but content-free film/TV ranking prose.
- Modify `web/components/content_input.py`: render and maintain editable scene cards and expose structured drafts in `video_params`.
- Modify `web/components/output_preview.py`: pass structured scene overrides to the generation pipeline while retaining legacy fallback.
- Modify `morpheus_video_studio/pipelines/standard.py`: consume narration and prompt overrides and skip redundant LLM prompt generation.
- Create `tests/test_scene_draft_generator.py`: generation orchestration, count validation, and partial failures.
- Create `tests/test_scene_draft_pipeline.py`: standard-pipeline override behavior.
- Modify `tests/test_content_input_scene_count.py`: session-state conversion, clearing, and legacy compatibility.
- Modify `tests/test_content_recipes.py`: film/TV narration requirements.

---

### Task 1: Scene Draft Model and Staged Generator

**Files:**
- Create: `morpheus_video_studio/models/scene_draft.py`
- Create: `morpheus_video_studio/services/scene_draft_generator.py`
- Create: `tests/test_scene_draft_generator.py`

**Interfaces:**
- Produces: `SceneDraft(index: int, narration: str, image_prompt: str = "", video_prompt: str = "")`
- Produces: `SceneDraft.to_dict() -> dict[str, object]`
- Produces: `SceneDraft.from_dict(value: dict) -> SceneDraft`
- Produces: `async generate_scene_drafts(llm_service, *, text: str, mode: str, n_scenes: int, min_words: int, max_words: int, content_recipe: str | None, visual_rules: str = "") -> SceneDraftGenerationResult`
- Produces: `SceneDraftGenerationResult(scenes: list[SceneDraft], errors: dict[str, str])`

- [ ] **Step 1: Write failing model and orchestration tests**

```python
import asyncio
from unittest.mock import AsyncMock, patch

from morpheus_video_studio.models.scene_draft import SceneDraft
from morpheus_video_studio.services.scene_draft_generator import generate_scene_drafts


def test_scene_draft_round_trips_through_dict() -> None:
    scene = SceneDraft(1, "旁白", "图片", "视频")
    assert SceneDraft.from_dict(scene.to_dict()) == scene


def test_generate_scene_drafts_aligns_all_three_outputs() -> None:
    with (
        patch("morpheus_video_studio.services.scene_draft_generator.generate_narrations_from_topic", new=AsyncMock(return_value=["旁白一", "旁白二"])),
        patch("morpheus_video_studio.services.scene_draft_generator.generate_image_prompts", new=AsyncMock(return_value=["图片一", "图片二"])),
        patch("morpheus_video_studio.services.scene_draft_generator.generate_video_prompts", new=AsyncMock(return_value=["视频一", "视频二"])),
    ):
        result = asyncio.run(generate_scene_drafts(object(), text="主题", mode="generate", n_scenes=2, min_words=20, max_words=40, content_recipe="ranking"))

    assert [scene.to_dict() for scene in result.scenes] == [
        {"index": 1, "narration": "旁白一", "image_prompt": "图片一", "video_prompt": "视频一"},
        {"index": 2, "narration": "旁白二", "image_prompt": "图片二", "video_prompt": "视频二"},
    ]
    assert result.errors == {}
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `pytest -q tests/test_scene_draft_generator.py`

Expected: collection fails because `morpheus_video_studio.models.scene_draft` does not exist.

- [ ] **Step 3: Implement the value objects and successful staged generation**

```python
# morpheus_video_studio/models/scene_draft.py
from dataclasses import dataclass


@dataclass
class SceneDraft:
    index: int
    narration: str
    image_prompt: str = ""
    video_prompt: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "narration": self.narration,
            "image_prompt": self.image_prompt,
            "video_prompt": self.video_prompt,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "SceneDraft":
        return cls(
            index=int(value["index"]),
            narration=str(value.get("narration", "")),
            image_prompt=str(value.get("image_prompt", "")),
            video_prompt=str(value.get("video_prompt", "")),
        )
```

In `scene_draft_generator.py`, resolve topic/document narration exactly as Quick Create currently does, then call `generate_image_prompts` and `generate_video_prompts` using the returned narration list. Validate each successful result with:

```python
def _require_aligned(values: list[str], expected: int, label: str) -> list[str]:
    if len(values) != expected:
        raise ValueError(f"{label}数量不匹配：需要 {expected} 条，实际 {len(values)} 条")
    return [str(value).strip() for value in values]
```

Return one-based `SceneDraft` objects and an empty error dictionary.

- [ ] **Step 4: Verify successful generation is GREEN**

Run: `pytest -q tests/test_scene_draft_generator.py`

Expected: 2 tests pass.

- [ ] **Step 5: Add failing tests for partial failure preservation**

```python
def test_image_prompt_failure_keeps_narration_and_video_prompts() -> None:
    with (
        patch("morpheus_video_studio.services.scene_draft_generator.generate_narrations_from_topic", new=AsyncMock(return_value=["旁白一", "旁白二"])),
        patch("morpheus_video_studio.services.scene_draft_generator.generate_image_prompts", new=AsyncMock(side_effect=RuntimeError("image failed"))),
        patch("morpheus_video_studio.services.scene_draft_generator.generate_video_prompts", new=AsyncMock(return_value=["视频一", "视频二"])),
    ):
        result = asyncio.run(generate_scene_drafts(object(), text="主题", mode="generate", n_scenes=2, min_words=20, max_words=40, content_recipe="general"))

    assert [scene.narration for scene in result.scenes] == ["旁白一", "旁白二"]
    assert [scene.image_prompt for scene in result.scenes] == ["", ""]
    assert [scene.video_prompt for scene in result.scenes] == ["视频一", "视频二"]
    assert "image_prompts" in result.errors
```

Add the mirror case for video-prompt failure and a count-mismatch case that records the failing stage while retaining other results.

- [ ] **Step 6: Implement independent visual-stage error capture**

Call each visual generator in its own `try/except`. Initialize missing values to `""`, record user-readable errors under `image_prompts` or `video_prompts`, and continue to the other stage. Do not catch narration errors; without narration there is no valid scene alignment.

- [ ] **Step 7: Run tests and commit**

Run: `pytest -q tests/test_scene_draft_generator.py`

Expected: all scene-draft generator tests pass.

```bash
git add morpheus_video_studio/models/scene_draft.py morpheus_video_studio/services/scene_draft_generator.py tests/test_scene_draft_generator.py
git commit -m "feat: generate aligned scene drafts"
```

---

### Task 2: Film/TV Explanation Prompt Guardrails

**Files:**
- Modify: `morpheus_video_studio/prompts/content_recipes.py`
- Modify: `morpheus_video_studio/utils/content_generators.py`
- Modify: `tests/test_content_recipes.py`
- Modify: `tests/test_narration_length_retry.py`

**Interfaces:**
- Consumes: `get_recipe_block("ranking") -> str`
- Produces: a ranking block that requires plot evidence rather than generic emotional language.

- [ ] **Step 1: Add failing prompt-content tests**

```python
def test_ranking_recipe_demands_film_explanation_not_emotional_filler() -> None:
    block = get_recipe_block("ranking")
    for requirement in ("具体人物", "人物行动", "剧情冲突", "关键场面", "入选理由"):
        assert requirement in block
    assert "不能用抽象情绪或人生感悟代替剧情介绍" in block
```

Extend the retry test so a correctly formatted but generic result such as `第1项：最温暖的一集｜它让我们看见平凡生活里的爱与成长` is rejected for film/TV ranking input.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `pytest -q tests/test_content_recipes.py tests/test_narration_length_retry.py`

Expected: the new concrete-film requirements and semantic validation assertions fail.

- [ ] **Step 3: Strengthen the recipe and ranking validation**

Add the exact concrete requirements to the ranking block. In `content_generators.py`, supplement structural validation for film/TV ranking topics with a conservative generic-copy detector: reject detail text containing multiple abstract-emotion terms but no concrete action/event marker. Keep the detector scoped to recognized ranking content so other creative categories are not constrained.

Use explicit constants:

```python
_ABSTRACT_EMOTION_TERMS = ("温暖", "治愈", "成长", "感动", "平凡生活", "人生感悟")
_CONCRETE_EVENT_TERMS = ("当", "为了", "却", "发现", "决定", "失去", "寻找", "面对", "阻止", "救", "离开", "回到")
```

- [ ] **Step 4: Run focused tests and commit**

Run: `pytest -q tests/test_content_recipes.py tests/test_narration_length_retry.py`

Expected: all focused tests pass.

```bash
git add morpheus_video_studio/prompts/content_recipes.py morpheus_video_studio/utils/content_generators.py tests/test_content_recipes.py tests/test_narration_length_retry.py
git commit -m "fix: require plot-specific screen narration"
```

---

### Task 3: Editable Scene Cards in Quick Create

**Files:**
- Modify: `web/components/content_input.py`
- Modify: `tests/test_content_input_scene_count.py`

**Interfaces:**
- Consumes: `generate_scene_drafts(...) -> SceneDraftGenerationResult`
- Produces: `video_params["scene_drafts"]: list[dict[str, object]]`
- Preserves: `video_params["ai_script_draft"]: str` as newline-joined narration for legacy consumers.

- [ ] **Step 1: Add failing state-helper tests**

Extract pure helpers and test them without rendering Streamlit:

```python
from web.components.content_input import scene_drafts_to_script, normalize_scene_drafts


def test_scene_drafts_to_script_uses_only_narration() -> None:
    drafts = [
        {"index": 1, "narration": "旁白一", "image_prompt": "图片一", "video_prompt": "视频一"},
        {"index": 2, "narration": "旁白二", "image_prompt": "图片二", "video_prompt": "视频二"},
    ]
    assert scene_drafts_to_script(drafts) == "旁白一\n旁白二"


def test_normalize_scene_drafts_repairs_indices_without_mixing_fields() -> None:
    result = normalize_scene_drafts([{"index": 8, "narration": "甲", "image_prompt": "图", "video_prompt": "动"}])
    assert result == [{"index": 1, "narration": "甲", "image_prompt": "图", "video_prompt": "动"}]
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `pytest -q tests/test_content_input_scene_count.py`

Expected: import errors for the two new helpers.

- [ ] **Step 3: Implement pure conversion helpers and structured generation call**

Replace `_generate_quick_create_draft` with `_generate_quick_create_scene_drafts`, returning the generator result. Store serialized scenes in `quick_create_scene_drafts`, errors in `quick_create_scene_draft_errors`, and keep `quick_create_ai_script_draft` synchronized through `scene_drafts_to_script`.

Extend `_clear_quick_create_draft()` to remove:

```python
"quick_create_scene_drafts",
"quick_create_scene_draft_errors",
```

- [ ] **Step 4: Render separate editable card fields**

For each scene, render a bordered container headed `分镜 {index}`. Use a narration text area outside the expander and an expander labelled `画面提示词` containing two text areas labelled `图片提示词` and `视频提示词`. Use stable keys:

```python
f"quick_scene_{index}_narration"
f"quick_scene_{index}_image_prompt"
f"quick_scene_{index}_video_prompt"
```

Before returning parameters, rebuild `scene_drafts` from the current widget values so edits are propagated. Display stage-specific warnings from `quick_create_scene_draft_errors` and a retry button that regenerates only missing prompt types by calling the corresponding existing generator with current narrations.

- [ ] **Step 5: Preserve stale-state and duration behavior**

Compute estimated duration from `scene_drafts_to_script(scene_drafts)`. Keep the existing source text/mode/scene metadata and stale warning. The success copy becomes `分镜草稿已生成；旁白和画面提示词可以分别修改。`

- [ ] **Step 6: Run focused tests and commit**

Run: `pytest -q tests/test_content_input_scene_count.py tests/test_scene_draft_generator.py`

Expected: all focused tests pass.

```bash
git add web/components/content_input.py tests/test_content_input_scene_count.py
git commit -m "feat: show editable scene prompt cards"
```

---

### Task 4: Reuse Edited Prompts in the Standard Pipeline

**Files:**
- Modify: `web/components/output_preview.py`
- Modify: `morpheus_video_studio/pipelines/standard.py`
- Create: `tests/test_scene_draft_pipeline.py`

**Interfaces:**
- Consumes: pipeline parameter `scene_drafts: list[dict[str, object]] | None`
- Produces: `ctx.narrations` from scene overrides during `generate_content`.
- Produces: `ctx.image_prompts` selected from `image_prompt` for image templates or `video_prompt` for video templates.
- Preserves: old `text` plus `mode="fixed"` behavior when `scene_drafts` is absent.

- [ ] **Step 1: Add failing pipeline override tests**

Construct a minimal pipeline context and verify:

```python
async def test_generate_content_uses_scene_draft_narrations_without_llm() -> None:
    ctx.params["scene_drafts"] = [
        {"index": 1, "narration": "用户旁白一", "image_prompt": "用户图片一", "video_prompt": "用户视频一"},
        {"index": 2, "narration": "用户旁白二", "image_prompt": "用户图片二", "video_prompt": "用户视频二"},
    ]
    await pipeline.generate_content(ctx)
    assert ctx.narrations == ["用户旁白一", "用户旁白二"]
    pipeline.llm.assert_not_awaited()
```

Add image-template and video-template tests that patch `generate_image_prompts` and `generate_video_prompts`, call `plan_visuals`, assert the corresponding user values populate `ctx.image_prompts`, and assert both generators were not called. Add a mismatch test expecting `ValueError("分镜草稿数量不匹配")`.

- [ ] **Step 2: Run the pipeline tests and verify RED**

Run: `pytest -q tests/test_scene_draft_pipeline.py`

Expected: the pipeline ignores `scene_drafts` and the assertions fail.

- [ ] **Step 3: Pass scene drafts from the output component**

Read `scene_drafts = video_params.get("scene_drafts") or []`. Include them in `gen_params` only when present. Keep `effective_text`, `effective_mode`, and `effective_split_mode` for legacy draft compatibility; structured drafts take precedence inside the pipeline.

- [ ] **Step 4: Consume and validate overrides in `generate_content`**

Add a focused helper on `StandardPipeline`:

```python
@staticmethod
def _validated_scene_drafts(params: dict) -> list[SceneDraft]:
    raw = params.get("scene_drafts") or []
    scenes = [SceneDraft.from_dict(item) for item in raw]
    if scenes and any(scene.index != index for index, scene in enumerate(scenes, 1)):
        raise ValueError("分镜草稿编号不连续")
    if scenes and any(not scene.narration.strip() for scene in scenes):
        raise ValueError("分镜草稿包含空旁白")
    return scenes
```

When scenes exist, require `len(scenes) == n_scenes`, assign their narrations, and return before mode-based generation.

- [ ] **Step 5: Select edited prompts in `plan_visuals`**

After resolving template type, check structured scenes before any stock or LLM prompt branch. For image templates select `scene.image_prompt`; for video templates select `scene.video_prompt`. Reject missing values with a message naming the scene and prompt type. Apply the configured prefix once using `build_image_prompt`, then return. Static templates retain `[None] * len(ctx.narrations)`.

- [ ] **Step 6: Run pipeline and output tests and commit**

Run: `pytest -q tests/test_scene_draft_pipeline.py tests/test_content_input_scene_count.py`

Expected: all focused tests pass, including no-regeneration assertions.

```bash
git add web/components/output_preview.py morpheus_video_studio/pipelines/standard.py tests/test_scene_draft_pipeline.py
git commit -m "feat: reuse edited scene prompts in video pipeline"
```

---

### Task 5: Full Regression and Browser Acceptance

**Files:**
- Modify only files implicated by failures from Tasks 1–4.

**Interfaces:**
- Verifies the complete Quick Create flow and backward compatibility.

- [ ] **Step 1: Run all automated tests**

Run: `pytest -q`

Expected: all tests pass with zero failures.

- [ ] **Step 2: Run syntax and diff checks**

Run:

```bash
python -m compileall -q morpheus_video_studio web tests
git diff --check
```

Expected: both commands exit 0 with no output.

- [ ] **Step 3: Exercise the original user case in the browser**

Open Quick Create and enter `《蜡笔小新》最感人的5集`, leave the target at 5 scenes, then generate the draft. Verify all of the following in the rendered page:

- exactly five numbered scene cards appear;
- each narration describes a concrete episode situation rather than generic life advice;
- each card has separately labelled image and video prompts;
- visual prompts are collapsed until opened;
- editing one prompt and rerendering preserves the edit;
- the stale warning appears after changing topic or scene count;
- clear removes narration and both prompt types.

- [ ] **Step 4: Verify final generation parameter handoff without spending media credits**

Use the existing test double around `morpheus_video_studio.generate_video` to click the generate action and inspect captured parameters. Confirm `scene_drafts` contains the edited narration/image/video values and no prompt generator is invoked. Do not call paid image/video backends during this acceptance check.

- [ ] **Step 5: Commit any acceptance fixes**

If acceptance required changes, rerun Steps 1–2, then:

```bash
git add morpheus_video_studio web tests
git commit -m "fix: complete scene draft handoff"
```

If no changes were required, do not create an empty commit.
