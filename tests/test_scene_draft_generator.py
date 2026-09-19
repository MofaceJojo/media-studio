import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from morpheus_video_studio.models.scene_draft import SceneDraft
from morpheus_video_studio.models.visual_scene_plan import VisualFact, VisualScenePlan
from morpheus_video_studio.services.scene_draft_generator import generate_scene_drafts
from morpheus_video_studio.services.visual_scene_planner import generate_visual_scene_plans


def _plan(number: int) -> VisualScenePlan:
    plan = VisualScenePlan(subject=VisualFact(source=f"对象{number}", english=f"object {number}"))
    plan.build_prompts()
    return plan


def test_visual_scene_planner_retries_invalid_json_then_returns_safe_aligned_plans() -> None:
    responses = iter(
        [
            '{"plans": []}',
            """{
              "plans": [{
                "index": 1,
                "subject": {"source": "红色自行车", "english": "red bicycle"},
                "location": {"source": "雨街", "english": "rainy street"},
                "action": {"source": "慢慢滚向门口", "english": "rolling slowly toward a doorway"},
                "outcome": {"source": "滚向门口", "english": "reaches a doorway"},
                "evidence": {"source": "水坑映出车轮", "english": "a puddle reflects its wheel"}
              }]
            }""",
            """{
              "plans": [{
                "index": 1,
                "faithful_translation": true,
                "english_only": true,
                "no_added_details": true,
                "issues": []
              }]
            }""",
        ]
    )
    received_calls: list[dict[str, object]] = []

    async def fake_llm(**kwargs: object) -> str:
        received_calls.append(kwargs)
        return next(responses)

    plans = asyncio.run(
        generate_visual_scene_plans(
            fake_llm,
            ["一辆红色自行车在雨街上慢慢滚向门口，水坑映出车轮。"],
            visual_rules="No people.",
        )
    )

    assert len(plans) == 1
    assert plans[0].subject.source == "红色自行车"
    assert "red bicycle" in plans[0].image_prompt
    assert "slow camera movement" in plans[0].video_prompt
    assert "巴黎" not in plans[0].image_prompt
    assert len(received_calls) == 3
    assert "No people." in str(received_calls[0]["prompt"])
    assert "symbolic" not in str(received_calls[0]["prompt"]).lower()
    assert "image_prompt" not in str(received_calls[0]["prompt"])
    assert "video_prompt" not in str(received_calls[0]["prompt"])
    assert received_calls[-1]["temperature"] == 0
    assert "faithful_translation" in str(received_calls[-1]["prompt"])


@pytest.mark.parametrize("field", ["location", "evidence"])
def test_visual_scene_planner_rejects_invented_facts_not_copied_from_narration(field: str) -> None:
    plan = {
        "index": 1,
        "subject": {"source": "红色自行车", "english": "red bicycle"},
        "location": {"source": "雨街", "english": "rainy street"},
        "action": {"source": "慢慢滚向门口", "english": "rolling toward a doorway"},
        "outcome": {"source": "滚向门口", "english": "reaches a doorway"},
        "evidence": {"source": "水坑映出车轮", "english": "a puddle reflects its wheel"},
    }
    plan[field] = {"source": "invented " + field, "english": "invented " + field}

    async def fake_llm(**_kwargs: object) -> str:
        import json
        return json.dumps({"plans": [plan]}, ensure_ascii=False)

    with pytest.raises(ValueError, match="visual-plan"):
        asyncio.run(
            generate_visual_scene_plans(
                fake_llm, ["红色自行车在雨街慢慢滚向门口，水坑映出车轮。"]
            )
        )


def test_visual_scene_planner_rejects_free_form_prompt_fields() -> None:
    response = {
        "plans": [{
            "index": 1,
            "subject": {"source": "红色自行车", "english": "red bicycle"},
            "location": {"source": "", "english": ""},
            "action": {"source": "", "english": ""},
            "outcome": {"source": "", "english": ""},
            "evidence": {"source": "", "english": ""},
            "image_prompt": "red bicycle in Paris rain",
        }]
    }

    async def fake_llm(**_kwargs: object) -> str:
        import json
        return json.dumps(response, ensure_ascii=False)

    with pytest.raises(ValueError, match="visual-plan"):
        asyncio.run(generate_visual_scene_plans(fake_llm, ["红色自行车"] ))


def test_visual_scene_planner_retries_when_judge_rejects_embellished_translation() -> None:
    plan_response = {
        "plans": [{
            "index": 1,
            "subject": {"source": "红色自行车", "english": "red bicycle near the Eiffel Tower in Paris"},
            "location": {"source": "", "english": ""},
            "action": {"source": "", "english": ""},
            "outcome": {"source": "", "english": ""},
            "evidence": {"source": "", "english": ""},
        }]
    }
    safe_plan_response = {
        "plans": [{
            **plan_response["plans"][0],
            "subject": {"source": "红色自行车", "english": "red bicycle"},
        }]
    }
    verdicts = iter([
        {"plans": [{"index": 1, "faithful_translation": False, "english_only": True, "no_added_details": False, "issues": ["Paris was added"]}]},
        {"plans": [{"index": 1, "faithful_translation": True, "english_only": True, "no_added_details": True, "issues": []}]},
    ])
    planning_calls = 0

    async def fake_llm(**kwargs: object) -> str:
        nonlocal planning_calls
        import json
        if kwargs["temperature"] == 0:
            return json.dumps(next(verdicts), ensure_ascii=False)
        planning_calls += 1
        return json.dumps(plan_response if planning_calls == 1 else safe_plan_response, ensure_ascii=False)

    plans = asyncio.run(generate_visual_scene_plans(fake_llm, ["红色自行车"]))

    assert planning_calls == 2
    assert "Eiffel Tower" not in plans[0].image_prompt


@pytest.mark.parametrize(
    "verdict",
    [
        "",
        "not json",
        {"plans": []},
        {"plans": [{"index": 1, "faithful_translation": True, "english_only": True, "no_added_details": True, "issues": [], "extra": True}]},
        {"plans": [{"index": 1, "faithful_translation": True, "english_only": False, "no_added_details": True, "issues": []}]},
    ],
)
def test_visual_scene_planner_rejects_invalid_or_unacceptable_judge_verdicts(verdict: object) -> None:
    plan_response = {
        "plans": [{
            "index": 1,
            "subject": {"source": "red bicycle", "english": "red bicycle"},
            "location": {"source": "", "english": ""},
            "action": {"source": "", "english": ""},
            "outcome": {"source": "", "english": ""},
            "evidence": {"source": "", "english": ""},
        }]
    }
    judge_calls = 0

    async def fake_llm(**kwargs: object) -> str:
        nonlocal judge_calls
        import json
        if kwargs["temperature"] == 0:
            judge_calls += 1
            return verdict if isinstance(verdict, str) else json.dumps(verdict)
        return json.dumps(plan_response)

    with pytest.raises(ValueError, match="visual-plan"):
        asyncio.run(generate_visual_scene_plans(fake_llm, ["red bicycle"]))

    assert judge_calls == 3


@pytest.mark.parametrize("narrations", [[None], ["   "], [123]])
def test_visual_scene_planner_rejects_non_string_or_blank_narrations(narrations: list[object]) -> None:
    async def should_not_run(**_kwargs: object) -> str:
        raise AssertionError("LLM must not be called for invalid narration")

    with pytest.raises(ValueError, match="narrations"):
        asyncio.run(generate_visual_scene_plans(should_not_run, narrations))


def test_visual_scene_planner_rejects_invalid_responses_after_retries() -> None:
    attempts = 0

    async def fake_llm(**_kwargs: object) -> str:
        nonlocal attempts
        attempts += 1
        return '{"plans": [{"index": 2}]}'

    with pytest.raises(ValueError, match="visual-plan"):
        asyncio.run(generate_visual_scene_plans(fake_llm, ["完整旁白"]))

    assert attempts == 3


def test_scene_draft_round_trips_through_dict() -> None:
    scene = SceneDraft(1, "旁白", "图片", "视频")

    assert SceneDraft.from_dict(scene.to_dict()) == scene


def test_generate_scene_drafts_converts_aligned_visual_plans() -> None:
    planner = AsyncMock(return_value=[_plan(1), _plan(2)])
    llm_service = object()
    with (
        patch(
            "morpheus_video_studio.services.scene_draft_generator."
            "generate_narrations_from_topic",
            new=AsyncMock(return_value=["旁白一", "旁白二"]),
        ),
        patch(
            "morpheus_video_studio.services.scene_draft_generator."
            "generate_visual_scene_plans",
            new=planner,
        ),
    ):
        result = asyncio.run(
            generate_scene_drafts(
                llm_service, text="主题", mode="generate", n_scenes=2,
                min_words=20, max_words=40, content_recipe="ranking", visual_rules="No faces.",
            )
        )

    assert [scene.narration for scene in result.scenes] == ["旁白一", "旁白二"]
    assert [scene.image_prompt for scene in result.scenes] == [
        _plan(1).image_prompt,
        _plan(2).image_prompt,
    ]
    assert [scene.video_prompt for scene in result.scenes] == [
        _plan(1).video_prompt,
        _plan(2).video_prompt,
    ]
    planner.assert_awaited_once_with(llm_service, ["旁白一", "旁白二"], visual_rules="No faces.")
    assert result.errors == {}


def test_scene_draft_generation_reports_narration_and_visual_plan_stages() -> None:
    reported_stages: list[str] = []
    with (
        patch(
            "morpheus_video_studio.services.scene_draft_generator."
            "generate_narrations_from_topic",
            new=AsyncMock(return_value=["旁白"]),
        ),
        patch(
            "morpheus_video_studio.services.scene_draft_generator."
            "generate_visual_scene_plans",
            new=AsyncMock(return_value=[_plan(1)]),
        ),
    ):
        asyncio.run(
            generate_scene_drafts(
                object(), text="主题", mode="generate", n_scenes=1,
                min_words=2, max_words=20, content_recipe="general",
                progress_callback=reported_stages.append,
            )
        )

    assert reported_stages == ["narration", "visual_plans"]


@pytest.mark.parametrize("content_recipe", ["general", None])
def test_topic_generation_resolves_numbered_rankings(content_recipe: str | None) -> None:
    llm_service = object()
    narration_generator = AsyncMock(return_value=["旁白一", "旁白二"])
    with (
        patch(
            "morpheus_video_studio.services.scene_draft_generator."
            "generate_narrations_from_topic",
            new=narration_generator,
        ),
        patch(
            "morpheus_video_studio.services.scene_draft_generator."
            "generate_visual_scene_plans",
            new=AsyncMock(return_value=[_plan(1), _plan(2)]),
        ),
    ):
        asyncio.run(
            generate_scene_drafts(
                llm_service, text="最感人的5集动画", mode="generate", n_scenes=2,
                min_words=20, max_words=40, content_recipe=content_recipe,
            )
        )

    narration_generator.assert_awaited_once_with(
        llm_service, topic="最感人的5集动画", n_scenes=2,
        min_words=20, max_words=40, content_recipe="ranking", strict_count=True,
    )


def test_scene_draft_generation_rejects_intro_plus_requested_entries() -> None:
    async def fake_llm(**_kwargs: object) -> str:
        return '{"narrations": ["欢迎观看本期盘点", "第一条具体内容", "第二条具体内容"]}'

    with pytest.raises(ValueError, match="需要 2 条，实际 3 条"):
        asyncio.run(
            generate_scene_drafts(
                fake_llm, text="普通主题", mode="generate", n_scenes=2,
                min_words=2, max_words=20, content_recipe="general",
            )
        )


def test_visual_plan_failure_keeps_narration_and_leaves_both_prompts_blank() -> None:
    with (
        patch(
            "morpheus_video_studio.services.scene_draft_generator."
            "generate_narrations_from_topic",
            new=AsyncMock(return_value=["旁白一", "旁白二"]),
        ),
        patch(
            "morpheus_video_studio.services.scene_draft_generator."
            "generate_visual_scene_plans",
            new=AsyncMock(side_effect=RuntimeError("invalid visual plan")),
        ),
    ):
        result = asyncio.run(
            generate_scene_drafts(
                object(), text="主题", mode="generate", n_scenes=2,
                min_words=20, max_words=40, content_recipe="general",
            )
        )

    assert [scene.narration for scene in result.scenes] == ["旁白一", "旁白二"]
    assert [scene.image_prompt for scene in result.scenes] == ["", ""]
    assert [scene.video_prompt for scene in result.scenes] == ["", ""]
    assert "visual_plans" in result.errors
