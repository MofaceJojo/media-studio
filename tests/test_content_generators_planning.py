import asyncio

from morpheus_video_studio.utils.content_generators import (
    estimate_scene_plan,
    split_narration_script,
)


def test_estimate_scene_plan_scales_with_long_text() -> None:
    text = "水浒传里有很多人物、很多事件、很多因果关系。" * 12

    plan = estimate_scene_plan(text, target_scene_seconds=6.0, min_scenes=3, max_scenes=30)

    assert plan["estimated_duration_seconds"] > 20
    assert plan["recommended_scenes"] > 3


def test_estimate_scene_plan_does_not_force_extra_scenes_for_short_text() -> None:
    plan = estimate_scene_plan("只讲一句话。", target_scene_seconds=8.0, min_scenes=1, max_scenes=30)

    assert plan["recommended_scenes"] == 1


def test_split_narration_script_auto_breaks_single_long_paragraph() -> None:
    script = (
        "第一句介绍背景。第二句补充人物关系。第三句说明冲突来源。"
        "第四句推进情节发展。第五句总结观点并引出下文。"
    )

    narrations = asyncio.run(
        split_narration_script(
            script,
            split_mode="auto",
            target_segments=4,
            max_chars_per_segment=18,
        )
    )

    assert len(narrations) >= 3
    assert all(item.strip() for item in narrations)
