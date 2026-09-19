import asyncio

import pytest

from morpheus_video_studio.models.visual_scene_plan import VisualFact, VisualScenePlan
from morpheus_video_studio.utils.visual_prompt_policy import (
    DEFAULT_SAFE_VISUAL_RULES,
    build_visual_rules,
    sanitize_visual_prompt,
)


def test_shared_rules_prefer_grounded_visuals_and_safe_humans() -> None:
    rules = build_visual_rules("Prefer a rainy street.")

    assert "objects" in DEFAULT_SAFE_VISUAL_RULES.lower()
    assert "environments" in DEFAULT_SAFE_VISUAL_RULES.lower()
    assert "reference imagery" in DEFAULT_SAFE_VISUAL_RULES.lower()
    assert "back views" in DEFAULT_SAFE_VISUAL_RULES.lower()
    assert "silhouettes" in DEFAULT_SAFE_VISUAL_RULES.lower()
    for prohibited in (
        "identifiable",
        "front-facing",
        "face",
        "eye",
        "hand",
        "finger",
        "multi-person",
    ):
        assert prohibited in DEFAULT_SAFE_VISUAL_RULES.lower()
    assert "concrete narration evidence" in DEFAULT_SAFE_VISUAL_RULES.lower()
    assert rules.endswith("Prefer a rainy street.")


def test_sanitizer_rewrites_fragile_human_compositions_without_losing_scene() -> None:
    prompt = (
        "close-up portrait with expressive eyes and detailed hands, "
        "two people embracing beside a red bicycle in a rainy street"
    )

    safe = sanitize_visual_prompt(prompt)

    assert "distant back-view silhouette" in safe
    assert "face fully turned away" in safe
    assert "hands outside the frame" in safe
    assert "two people embracing" not in safe.lower()
    assert "red bicycle" in safe
    assert "rainy street" in safe


def test_sanitizer_rewrites_face_and_hand_variants_without_losing_objects() -> None:
    prompt = (
        "front-facing portrait, visible face and eyes, hands and fingers on "
        "a red bicycle in a rainy street"
    )

    safe = sanitize_visual_prompt(prompt)

    for unsafe in ("front-facing", "portrait", "visible face", "eyes", "visible hands", "fingers on"):
        assert unsafe not in safe.lower()
    assert "face fully turned away" in safe
    assert "hands outside the frame" in safe
    assert "red bicycle" in safe
    assert "rainy street" in safe


def test_sanitizer_converts_a_woman_to_an_occluded_safe_depiction() -> None:
    safe = sanitize_visual_prompt("a woman walking on a street beside a red bicycle")

    assert "woman" not in safe.lower()
    assert "distant back-view silhouette" in safe
    assert "face fully turned away" in safe
    assert "hands outside the frame" in safe
    assert "street" in safe
    assert "red bicycle" in safe


def test_visual_scene_plan_requires_a_nonblank_bilingual_subject_pair() -> None:
    with pytest.raises(ValueError, match="subject"):
        VisualScenePlan(subject=VisualFact())

    with pytest.raises(ValueError, match="paired"):
        VisualFact(source="红色自行车", english="")


def test_visual_scene_plan_builds_english_prompts_only_from_fact_translations() -> None:
    plan = VisualScenePlan(
        subject=VisualFact(source="红色自行车", english="red bicycle"),
        location=VisualFact(source="雨街", english="rainy street"),
        action=VisualFact(source="慢慢滚动", english="rolling slowly"),
    )
    plan.build_prompts()

    assert "red bicycle" in plan.image_prompt
    assert "rainy street" in plan.video_prompt
    assert "rolling slowly" in plan.video_prompt
    assert "红色自行车" not in plan.image_prompt
    assert "雨街" not in plan.video_prompt
    assert "slow camera movement" in plan.video_prompt
    assert "fully turned away fully" not in plan.image_prompt


def test_image_prompt_builder_never_allows_small_or_conditional_faces() -> None:
    from morpheus_video_studio.prompts.image_generation import build_image_prompt_prompt

    prompt = build_image_prompt_prompt(["narration"], 20, 40)

    assert "small-to-medium" not in prompt
    assert "if emotion allows" not in prompt
    assert "identifiable" in prompt.lower()


@pytest.mark.parametrize("generator_name", ["generate_image_prompts", "generate_video_prompts"])
def test_legacy_generators_sanitize_every_returned_prompt(generator_name: str) -> None:
    from morpheus_video_studio.utils import content_generators

    generator = getattr(content_generators, generator_name)
    key = "image_prompts" if generator_name == "generate_image_prompts" else "video_prompts"

    async def fake_llm(**_kwargs: object) -> str:
        return (
            '{"' + key + '":["front view portrait with visible hands, red bicycle in rainy street"]}'
        )

    prompts = asyncio.run(generator(fake_llm, ["narration"], max_retries=1))

    assert "front view" not in prompts[0].lower()
    assert "portrait" not in prompts[0].lower()
    assert "visible hands" not in prompts[0].lower()
    assert "red bicycle" in prompts[0]
    assert "rainy street" in prompts[0]
