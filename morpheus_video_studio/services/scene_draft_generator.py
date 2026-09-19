from collections.abc import Callable
from dataclasses import dataclass

from morpheus_video_studio.models.scene_draft import SceneDraft
from morpheus_video_studio.prompts.content_recipes import resolve_content_recipe
from morpheus_video_studio.services.visual_scene_planner import generate_visual_scene_plans
from morpheus_video_studio.utils.content_generators import (
    generate_narrations_from_content,
    generate_narrations_from_topic,
)


@dataclass
class SceneDraftGenerationResult:
    scenes: list[SceneDraft]
    errors: dict[str, str]


def _require_aligned(values: list[object], expected: int, label: str) -> list[str]:
    if len(values) != expected:
        raise ValueError(f"{label}数量不匹配：需要 {expected} 条，实际 {len(values)} 条")
    normalized = ["" if value is None else str(value).strip() for value in values]
    blank_indexes = [
        str(index)
        for index, value in enumerate(normalized, start=1)
        if not value
    ]
    if blank_indexes:
        raise ValueError(f"{label}包含空内容：第 {', '.join(blank_indexes)} 条")
    return normalized


async def generate_scene_drafts(
    llm_service,
    *,
    text: str,
    mode: str,
    n_scenes: int,
    min_words: int,
    max_words: int,
    content_recipe: str | None,
    visual_rules: str = "",
    progress_callback: Callable[[str], None] | None = None,
) -> SceneDraftGenerationResult:
    if progress_callback:
        progress_callback("narration")
    if mode == "document":
        narrations = await generate_narrations_from_content(
            llm_service,
            content=text,
            n_scenes=n_scenes,
            min_words=min_words,
            max_words=max_words,
            strict_count=True,
        )
    else:
        narrations = await generate_narrations_from_topic(
            llm_service,
            topic=text,
            n_scenes=n_scenes,
            min_words=min_words,
            max_words=max_words,
            content_recipe=resolve_content_recipe(text, content_recipe),
            strict_count=True,
        )
    narrations = _require_aligned(narrations, n_scenes, "旁白")

    image_prompts = [""] * n_scenes
    video_prompts = [""] * n_scenes
    errors: dict[str, str] = {}

    if progress_callback:
        progress_callback("visual_plans")
    try:
        plans = await generate_visual_scene_plans(
            llm_service, narrations, visual_rules=visual_rules
        )
        if len(plans) != n_scenes:
            raise ValueError(
                f"视觉方案数量不匹配：需要 {n_scenes} 条，实际 {len(plans)} 条"
            )
        image_prompts = [plan.image_prompt for plan in plans]
        video_prompts = [plan.video_prompt for plan in plans]
    except Exception as exc:
        errors["visual_plans"] = f"视觉方案生成失败：{exc}"

    scenes = [
        SceneDraft(index + 1, narration, image_prompts[index], video_prompts[index])
        for index, narration in enumerate(narrations)
    ]
    return SceneDraftGenerationResult(scenes=scenes, errors=errors)
