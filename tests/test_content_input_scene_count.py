from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from web.components.content_input import (
    _clear_quick_create_draft,
    _draft_is_stale,
    _generate_quick_create_scene_drafts,
    _missing_scene_prompt_types,
    _retry_missing_scene_prompts,
    _scene_draft_completion_status,
    _scene_draft_stage_label,
    normalize_scene_drafts,
    resolve_effective_scene_count,
    resolve_narration_length_bounds,
    scene_drafts_to_script,
)


def test_scene_drafts_to_script_uses_only_narration() -> None:
    drafts = [
        {"index": 1, "narration": "旁白一", "image_prompt": "图片一", "video_prompt": "视频一"},
        {"index": 2, "narration": "旁白二", "image_prompt": "图片二", "video_prompt": "视频二"},
    ]

    assert scene_drafts_to_script(drafts) == "旁白一\n旁白二"


def test_normalize_scene_drafts_repairs_indices_without_mixing_fields() -> None:
    result = normalize_scene_drafts(
        [{"index": 8, "narration": "甲", "image_prompt": "图", "video_prompt": "动"}]
    )

    assert result == [
        {"index": 1, "narration": "甲", "image_prompt": "图", "video_prompt": "动"}
    ]


def test_normalize_scene_drafts_treats_none_text_as_empty() -> None:
    result = normalize_scene_drafts(
        [
            {
                "index": 1,
                "narration": None,
                "image_prompt": None,
                "video_prompt": None,
            }
        ]
    )

    assert result == [
        {"index": 1, "narration": "", "image_prompt": "", "video_prompt": ""}
    ]


def test_quick_create_generation_uses_structured_scene_generator() -> None:
    expected = object()
    generator = AsyncMock(return_value=expected)
    progress_callback = MagicMock()

    with patch(
        "web.components.content_input.generate_scene_drafts",
        new=generator,
    ):
        result = _generate_quick_create_scene_drafts(
            SimpleNamespace(llm="llm"),
            text="主题",
            mode="generate",
            n_scenes=3,
            content_recipe="general",
            target_scene_seconds=6,
            progress_callback=progress_callback,
        )

    assert result is expected
    generator.assert_awaited_once_with(
        "llm",
        text="主题",
        mode="generate",
        n_scenes=3,
        min_words=18,
        max_words=30,
        content_recipe="general",
        visual_rules="",
        progress_callback=progress_callback,
    )


def test_scene_draft_stage_labels_are_visible_and_specific() -> None:
    assert _scene_draft_stage_label("narration") == "正在生成解说..."
    assert _scene_draft_stage_label("image_prompts") == "正在生成图片提示词..."
    assert _scene_draft_stage_label("video_prompts") == "正在生成视频提示词..."


def test_scene_draft_completion_status_surfaces_partial_visual_failure() -> None:
    assert _scene_draft_completion_status({}) == ("分镜草稿生成完成", "complete")
    assert _scene_draft_completion_status(
        {"image_prompts": "图片提示词生成失败"}
    ) == ("分镜草稿已生成，但部分画面提示词失败", "error")


def test_retry_missing_scene_prompts_only_regenerates_failed_stage() -> None:
    image_generator = AsyncMock(return_value=["新图"])
    video_generator = AsyncMock(return_value=["不应该生成"])
    drafts = [
        {"index": 1, "narration": "旁白一", "image_prompt": "", "video_prompt": "原视频一"},
        {
            "index": 2,
            "narration": "旁白二",
            "image_prompt": "用户编辑图",
            "video_prompt": "原视频二",
        },
    ]

    with (
        patch(
            "web.components.content_input.generate_image_prompts",
            new=image_generator,
        ),
        patch(
            "web.components.content_input.generate_video_prompts",
            new=video_generator,
        ),
    ):
        scenes, errors = _retry_missing_scene_prompts(
            SimpleNamespace(llm="llm"),
            drafts,
            {"image_prompts": "之前失败"},
            min_words=18,
            max_words=30,
            visual_rules="",
        )

    assert scenes == [
        {
            "index": 1,
            "narration": "旁白一",
            "image_prompt": "新图",
            "video_prompt": "原视频一",
        },
        {
            "index": 2,
            "narration": "旁白二",
            "image_prompt": "用户编辑图",
            "video_prompt": "原视频二",
        },
    ]
    assert errors == {}
    image_generator.assert_awaited_once_with(
        "llm",
        narrations=["旁白一"],
        min_words=18,
        max_words=30,
        visual_rules="",
    )
    video_generator.assert_not_awaited()


def test_retry_missing_scene_prompts_fills_manual_empty_without_stage_error() -> None:
    image_generator = AsyncMock(return_value=["不应该生成"])
    video_generator = AsyncMock(return_value=["补生成的视频提示词"])
    drafts = [
        {
            "index": 1,
            "narration": "旁白",
            "image_prompt": "用户图片",
            "video_prompt": "   ",
        }
    ]

    with (
        patch(
            "web.components.content_input.generate_image_prompts",
            new=image_generator,
        ),
        patch(
            "web.components.content_input.generate_video_prompts",
            new=video_generator,
        ),
    ):
        scenes, errors = _retry_missing_scene_prompts(
            SimpleNamespace(llm="llm"),
            drafts,
            {},
            min_words=18,
            max_words=30,
            visual_rules="",
        )

    assert scenes == [
        {
            "index": 1,
            "narration": "旁白",
            "image_prompt": "用户图片",
            "video_prompt": "补生成的视频提示词",
        }
    ]
    assert errors == {}
    image_generator.assert_not_awaited()
    video_generator.assert_awaited_once_with(
        "llm",
        narrations=["旁白"],
        min_words=18,
        max_words=30,
    )


def test_manual_empty_prompt_exposes_retry_without_stage_error() -> None:
    drafts = [
        {
            "index": 1,
            "narration": "旁白",
            "image_prompt": "",
            "video_prompt": "用户视频",
        }
    ]

    assert _missing_scene_prompt_types(drafts) == {"image_prompts"}


def test_retry_blank_generated_prompt_keeps_stage_error() -> None:
    with (
        patch(
            "web.components.content_input.generate_image_prompts",
            new=AsyncMock(return_value=[None]),
        ),
        patch(
            "web.components.content_input.generate_video_prompts",
            new=AsyncMock(),
        ),
    ):
        scenes, errors = _retry_missing_scene_prompts(
            SimpleNamespace(llm="llm"),
            [
                {
                    "index": 1,
                    "narration": "旁白",
                    "image_prompt": "",
                    "video_prompt": "用户视频",
                }
            ],
            {},
            min_words=18,
            max_words=30,
            visual_rules="",
        )

    assert scenes[0]["image_prompt"] == ""
    assert "image_prompts" in errors


def test_clear_quick_create_draft_removes_structured_and_widget_state() -> None:
    state = {
        "quick_create_ai_script_draft": "旁白",
        "quick_create_scene_drafts": [{"index": 1}],
        "quick_create_scene_draft_errors": {"image_prompts": "failed"},
        "quick_create_ai_script_source_recipe": "ranking",
        "quick_scene_1_narration": "旁白",
        "quick_scene_1_image_prompt": "图",
        "quick_scene_1_video_prompt": "动",
        "quick_create_mode": "generate",
    }

    with patch("web.components.content_input.st.session_state", state):
        _clear_quick_create_draft()

    assert state == {"quick_create_mode": "generate"}


def test_draft_is_stale_when_only_effective_recipe_changes() -> None:
    state = {
        "quick_create_ai_script_source_text": "同一主题",
        "quick_create_ai_script_source_mode": "generate",
        "quick_create_ai_script_source_scenes": 5,
        "quick_create_ai_script_source_recipe": "general",
    }

    with patch("web.components.content_input.st.session_state", state):
        assert _draft_is_stale("同一主题", "generate", 5, "ranking") is True
        assert _draft_is_stale("同一主题", "generate", 5, "general") is False


def test_topic_mode_respects_selected_scene_count_for_short_topic() -> None:
    planning = {"recommended_scenes": 1}

    assert resolve_effective_scene_count("generate", 5, planning) == 5


def test_document_mode_can_use_length_based_scene_count() -> None:
    planning = {"recommended_scenes": 12}

    assert resolve_effective_scene_count("document", 5, planning) == 12


def test_document_mode_falls_back_to_selected_count_without_plan() -> None:
    assert resolve_effective_scene_count("document", 7, None) == 7


def test_draft_length_tracks_target_scene_duration() -> None:
    assert resolve_narration_length_bounds(6) == (18, 30)
    assert resolve_narration_length_bounds(10) == (30, 50)
