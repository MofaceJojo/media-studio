from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from morpheus_video_studio.models.scene_draft import SceneDraft
from morpheus_video_studio.pipelines.linear import PipelineContext
from morpheus_video_studio.pipelines.standard import StandardPipeline
from web.components.output_preview import render_batch_output, render_single_output

SCENE_DRAFTS = [
    {
        "index": 1,
        "narration": "用户旁白一",
        "image_prompt": "用户图片一",
        "video_prompt": "用户视频一",
    },
    {
        "index": 2,
        "narration": "用户旁白二",
        "image_prompt": "用户图片二",
        "video_prompt": "用户视频二",
    },
]


def _pipeline() -> StandardPipeline:
    core = SimpleNamespace(
        llm=AsyncMock(),
        tts=None,
        media=None,
        video=None,
        config={
            "comfyui": {
                "image": {"prompt_prefix": "默认图片风格"},
                "video": {"prompt_prefix": "默认视频风格"},
            }
        },
    )
    return StandardPipeline(core)


async def test_generate_content_uses_scene_draft_narrations_without_llm() -> None:
    pipeline = _pipeline()
    ctx = PipelineContext(
        input_text="原始主题",
        params={"mode": "generate", "n_scenes": 2, "scene_drafts": SCENE_DRAFTS},
    )
    narration_generator = AsyncMock(return_value=["重新生成一", "重新生成二"])

    with patch(
        "morpheus_video_studio.pipelines.standard.generate_narrations_from_topic",
        new=narration_generator,
    ):
        await pipeline.generate_content(ctx)

    assert ctx.narrations == ["用户旁白一", "用户旁白二"]
    narration_generator.assert_not_awaited()
    pipeline.llm.assert_not_awaited()


async def test_generate_content_rejects_scene_draft_count_mismatch() -> None:
    pipeline = _pipeline()
    ctx = PipelineContext(
        input_text="原始主题",
        params={"mode": "generate", "n_scenes": 3, "scene_drafts": SCENE_DRAFTS},
    )
    narration_generator = AsyncMock(return_value=["一", "二", "三"])

    with (
        patch(
            "morpheus_video_studio.pipelines.standard.generate_narrations_from_topic",
            new=narration_generator,
        ),
        pytest.raises(ValueError, match="^分镜草稿数量不匹配$"),
    ):
        await pipeline.generate_content(ctx)

    narration_generator.assert_not_awaited()


@pytest.mark.parametrize(
    ("scene_drafts", "message"),
    [
        ([{**SCENE_DRAFTS[0], "index": 2}], "分镜草稿编号不连续"),
        ([{**SCENE_DRAFTS[0], "narration": "  "}], "分镜 1 缺少旁白"),
        ([{**SCENE_DRAFTS[0], "narration": None}], "分镜 1 缺少旁白"),
    ],
)
async def test_generate_content_validates_scene_drafts(
    scene_drafts: list[dict[str, object]], message: str
) -> None:
    pipeline = _pipeline()
    ctx = PipelineContext(
        input_text="原始主题",
        params={"mode": "generate", "n_scenes": 1, "scene_drafts": scene_drafts},
    )
    narration_generator = AsyncMock(return_value=["生成旁白"])

    with (
        patch(
            "morpheus_video_studio.pipelines.standard.generate_narrations_from_topic",
            new=narration_generator,
        ),
        pytest.raises(ValueError, match=f"^{message}$"),
    ):
        await pipeline.generate_content(ctx)


def test_scene_draft_from_dict_treats_null_text_fields_as_empty() -> None:
    scene = SceneDraft.from_dict(
        {
            "index": 1,
            "narration": None,
            "image_prompt": None,
            "video_prompt": None,
        }
    )

    assert scene == SceneDraft(1, "", "", "")


async def test_generate_content_keeps_legacy_fixed_text_draft_behavior() -> None:
    pipeline = _pipeline()
    ctx = PipelineContext(
        input_text="旧旁白一\n旧旁白二",
        params={"mode": "fixed", "n_scenes": 2, "split_mode": "line"},
    )
    splitter = AsyncMock(return_value=["旧旁白一", "旧旁白二"])

    with patch(
        "morpheus_video_studio.pipelines.standard.split_narration_script",
        new=splitter,
    ):
        await pipeline.generate_content(ctx)

    assert ctx.narrations == ["旧旁白一", "旧旁白二"]
    splitter.assert_awaited_once_with(
        "旧旁白一\n旧旁白二",
        split_mode="line",
        target_segments=2,
        max_chars_per_segment=60,
    )


async def test_plan_visuals_uses_edited_image_prompts_before_stock_branch() -> None:
    pipeline = _pipeline()
    ctx = PipelineContext(
        input_text="原始主题",
        params={
            "scene_drafts": SCENE_DRAFTS,
            "frame_template": "1080x1920/image_default.html",
            "media_workflow": "stock/all",
            "prompt_prefix": "定制风格",
        },
        title="标题",
        narrations=["用户旁白一", "用户旁白二"],
    )
    image_generator = AsyncMock()
    video_generator = AsyncMock()

    with (
        patch(
            "morpheus_video_studio.pipelines.standard.generate_image_prompts",
            new=image_generator,
        ),
        patch(
            "morpheus_video_studio.pipelines.standard.generate_video_prompts",
            new=video_generator,
        ),
    ):
        await pipeline.plan_visuals(ctx)

    assert ctx.image_prompts == ["定制风格, 用户图片一", "定制风格, 用户图片二"]
    image_generator.assert_not_awaited()
    video_generator.assert_not_awaited()


async def test_plan_visuals_uses_edited_video_prompts_and_video_prefix() -> None:
    pipeline = _pipeline()
    ctx = PipelineContext(
        input_text="原始主题",
        params={
            "scene_drafts": SCENE_DRAFTS,
            "frame_template": "1080x1920/video_default.html",
        },
        narrations=["用户旁白一", "用户旁白二"],
    )
    image_generator = AsyncMock()
    video_generator = AsyncMock()

    with (
        patch(
            "morpheus_video_studio.pipelines.standard.generate_image_prompts",
            new=image_generator,
        ),
        patch(
            "morpheus_video_studio.pipelines.standard.generate_video_prompts",
            new=video_generator,
        ),
    ):
        await pipeline.plan_visuals(ctx)

    assert ctx.image_prompts == [
        "默认视频风格, 用户视频一",
        "默认视频风格, 用户视频二",
    ]
    image_generator.assert_not_awaited()
    video_generator.assert_not_awaited()


async def test_plan_visuals_keeps_static_templates_media_free() -> None:
    pipeline = _pipeline()
    ctx = PipelineContext(
        input_text="原始主题",
        params={
            "scene_drafts": SCENE_DRAFTS,
            "frame_template": "1080x1920/static_simple.html",
        },
        narrations=["用户旁白一", "用户旁白二"],
    )
    image_generator = AsyncMock()
    video_generator = AsyncMock()

    with (
        patch(
            "morpheus_video_studio.pipelines.standard.generate_image_prompts",
            new=image_generator,
        ),
        patch(
            "morpheus_video_studio.pipelines.standard.generate_video_prompts",
            new=video_generator,
        ),
    ):
        await pipeline.plan_visuals(ctx)

    assert ctx.image_prompts == [None, None]
    image_generator.assert_not_awaited()
    video_generator.assert_not_awaited()


@pytest.mark.parametrize(
    ("template", "missing_field", "prompt_type"),
    [
        ("image_default.html", "image_prompt", "图片提示词"),
        ("video_default.html", "video_prompt", "视频提示词"),
    ],
)
async def test_plan_visuals_rejects_missing_edited_prompt(
    template: str, missing_field: str, prompt_type: str
) -> None:
    pipeline = _pipeline()
    scene_drafts = [{**SCENE_DRAFTS[0], missing_field: "  "}]
    ctx = PipelineContext(
        input_text="原始主题",
        params={"scene_drafts": scene_drafts, "frame_template": template},
        narrations=["用户旁白一"],
    )
    image_generator = AsyncMock(return_value=["生成图片"])
    video_generator = AsyncMock(return_value=["生成视频"])

    with (
        patch(
            "morpheus_video_studio.pipelines.standard.generate_image_prompts",
            new=image_generator,
        ),
        patch(
            "morpheus_video_studio.pipelines.standard.generate_video_prompts",
            new=video_generator,
        ),
        pytest.raises(ValueError, match=rf"^分镜 1 缺少{prompt_type}$"),
    ):
        await pipeline.plan_visuals(ctx)


@pytest.mark.parametrize(
    ("template", "missing_field", "prompt_type"),
    [
        ("image_default.html", "image_prompt", "图片提示词"),
        ("video_default.html", "video_prompt", "视频提示词"),
    ],
)
async def test_plan_visuals_rejects_null_edited_prompt(
    template: str, missing_field: str, prompt_type: str
) -> None:
    pipeline = _pipeline()
    scene_drafts = [{**SCENE_DRAFTS[0], missing_field: None}]
    ctx = PipelineContext(
        input_text="原始主题",
        params={"scene_drafts": scene_drafts, "frame_template": template},
        narrations=["用户旁白一"],
    )

    with pytest.raises(ValueError, match=rf"^分镜 1 缺少{prompt_type}$"):
        await pipeline.plan_visuals(ctx)


def test_output_preview_passes_scene_drafts_to_video_generation() -> None:
    video_studio = MagicMock()
    generation = object()
    video_studio.generate_video.return_value = generation
    video_params = {
        "text": "原始主题",
        "mode": "generate",
        "n_scenes": 2,
        "scene_drafts": SCENE_DRAFTS,
        "ai_script_draft": "用户旁白一\n用户旁白二",
        "content_recipe": "ranking",
    }

    with (
        patch("web.components.output_preview.st") as streamlit,
        patch("web.components.output_preview.config_manager.validate", return_value=True),
        patch("web.components.output_preview.run_async", side_effect=RuntimeError("stop")),
        patch("web.components.output_preview.logger.exception"),
    ):
        streamlit.session_state = {}
        streamlit.button.return_value = True
        render_single_output(video_studio, video_params)

    kwargs = video_studio.generate_video.call_args.kwargs
    assert kwargs["scene_drafts"] == SCENE_DRAFTS
    assert kwargs["text"] == "用户旁白一\n用户旁白二"
    assert kwargs["mode"] == "fixed"
    assert kwargs["split_mode"] == "line"
    assert kwargs["content_recipe"] == "ranking"


def test_single_output_accepts_structured_draft_when_original_topic_is_empty() -> None:
    video_studio = MagicMock()
    video_params = {
        "text": "",
        "mode": "generate",
        "n_scenes": 2,
        "scene_drafts": SCENE_DRAFTS,
        "content_recipe": "ranking",
    }

    with (
        patch("web.components.output_preview.st") as streamlit,
        patch("web.components.output_preview.tr", side_effect=lambda key, **_kwargs: key),
        patch("web.components.output_preview.config_manager.validate", return_value=True),
        patch("web.components.output_preview.run_async", side_effect=RuntimeError("stop")),
        patch("web.components.output_preview.logger.exception"),
    ):
        streamlit.session_state = {}
        streamlit.button.return_value = True
        render_single_output(video_studio, video_params)

    kwargs = video_studio.generate_video.call_args.kwargs
    assert kwargs["text"] == "用户旁白一\n用户旁白二"
    assert kwargs["mode"] == "fixed"
    assert kwargs["split_mode"] == "line"
    assert all(
        call.args != ("error.input_required",) for call in streamlit.error.call_args_list
    )


def test_single_output_accepts_legacy_draft_when_original_topic_is_empty() -> None:
    video_studio = MagicMock()
    video_params = {
        "text": "",
        "mode": "generate",
        "n_scenes": 2,
        "ai_script_draft": "旧旁白一\n旧旁白二",
    }

    with (
        patch("web.components.output_preview.st") as streamlit,
        patch("web.components.output_preview.tr", side_effect=lambda key, **_kwargs: key),
        patch("web.components.output_preview.config_manager.validate", return_value=True),
        patch("web.components.output_preview.run_async", side_effect=RuntimeError("stop")),
        patch("web.components.output_preview.logger.exception"),
    ):
        streamlit.session_state = {}
        streamlit.button.return_value = True
        render_single_output(video_studio, video_params)

    kwargs = video_studio.generate_video.call_args.kwargs
    assert kwargs["text"] == "旧旁白一\n旧旁白二"
    assert kwargs["mode"] == "fixed"
    assert all(
        call.args != ("error.input_required",) for call in streamlit.error.call_args_list
    )


def test_batch_output_reuses_edited_scene_drafts_for_every_variant() -> None:
    video_studio = MagicMock()
    generated_result = SimpleNamespace(video_path="/tmp/task/final.mp4")
    video_studio.generate_video.return_value = object()
    video_params = {
        "topics": ["", ""],
        "mode": "generate",
        "n_scenes": 2,
        "scene_drafts": SCENE_DRAFTS,
        "content_recipe": "ranking",
    }

    with (
        patch("web.components.output_preview.st") as streamlit,
        patch("web.components.output_preview.config_manager.validate", return_value=True),
        patch("web.utils.async_helpers.run_async", return_value=generated_result),
    ):
        streamlit.button.return_value = True
        streamlit.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
        render_batch_output(video_studio, video_params)

    assert video_studio.generate_video.call_count == 2
    for call in video_studio.generate_video.call_args_list:
        assert call.kwargs["scene_drafts"] == SCENE_DRAFTS
        assert call.kwargs["text"] == "用户旁白一\n用户旁白二"
        assert call.kwargs["mode"] == "fixed"
        assert call.kwargs["split_mode"] == "line"
        assert call.kwargs["content_recipe"] == "ranking"


def test_batch_output_still_requires_manual_topics_without_reusable_draft() -> None:
    video_studio = MagicMock()
    video_params = {"topics": [""], "mode": "generate", "n_scenes": 2}

    with (
        patch("web.components.output_preview.st") as streamlit,
        patch("web.components.output_preview.config_manager.validate", return_value=True),
    ):
        streamlit.button.return_value = True
        render_batch_output(video_studio, video_params)

    video_studio.generate_video.assert_not_called()
    streamlit.warning.assert_called_once()
