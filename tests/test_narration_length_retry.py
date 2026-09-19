import asyncio
import json

import pytest

from morpheus_video_studio.utils.content_generators import (
    generate_narrations_from_content,
    generate_narrations_from_topic,
)

_SCREEN_JUDGE_MARKER = "影视盘点语义判定"


def _judge_item(
    index: int,
    *,
    identifiable_character: bool = True,
    external_situation: bool = True,
    observable_action: bool = True,
    event_supported_reason: bool = True,
    issues: list[str] | None = None,
) -> dict[str, object]:
    return {
        "index": index,
        "identifiable_character": identifiable_character,
        "external_situation": external_situation,
        "observable_action_or_conflict_with_object_or_result": observable_action,
        "event_supported_reason": event_supported_reason,
        "issues": list(issues or []),
    }


def _judge_response(*items: dict[str, object]) -> str:
    return json.dumps({"items": list(items)}, ensure_ascii=False)


def _accepted_judge_response(count: int) -> str:
    return _judge_response(*(_judge_item(index) for index in range(1, count + 1)))


def _rejected_judge_response(count: int, issue: str) -> str:
    return _judge_response(
        *(
            _judge_item(
                index,
                identifiable_character=False,
                external_situation=False,
                observable_action=False,
                event_supported_reason=False,
                issues=[issue],
            )
            for index in range(1, count + 1)
        )
    )


class _ControlledScreenRankingLLM:
    def __init__(
        self,
        generation_responses: list[str],
        judge_responses: list[str],
    ) -> None:
        self._generation_responses = iter(generation_responses)
        self._judge_responses = iter(judge_responses)
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def __call__(self, *, prompt: str, **kwargs) -> str:
        self.calls.append((prompt, kwargs))
        if _SCREEN_JUDGE_MARKER in prompt:
            return next(self._judge_responses)
        return next(self._generation_responses)

    @property
    def generation_calls(self) -> list[tuple[str, dict[str, object]]]:
        return [call for call in self.calls if _SCREEN_JUDGE_MARKER not in call[0]]

    @property
    def judge_calls(self) -> list[tuple[str, dict[str, object]]]:
        return [call for call in self.calls if _SCREEN_JUDGE_MARKER in call[0]]


def test_topic_generation_rewrites_narrations_that_are_too_short() -> None:
    responses = iter(
        [
            json.dumps({"narrations": ["搞笑片段"] * 3}, ensure_ascii=False),
            json.dumps(
                {
                    "narrations": [
                        "小新一本正经地解释自己的恶作剧，结果每句话都让美伢越来越生气",
                        "他以为躲到桌子下面就安全了，却忘了露在外面的屁股早已暴露位置",
                        "最后小新用一句天真的道歉化解危机，也让全家忍不住一起笑了起来",
                    ]
                },
                ensure_ascii=False,
            ),
        ]
    )
    prompts: list[str] = []

    async def fake_llm(*, prompt: str, **_kwargs) -> str:
        prompts.append(prompt)
        return next(responses)

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="小新搞笑片段",
            n_scenes=3,
            min_words=18,
            max_words=30,
        )
    )

    assert len(prompts) == 2
    assert "过短" in prompts[1]
    assert all(len(item) >= 18 for item in narrations)


def test_ranking_generation_rewrites_generic_prose_without_named_items() -> None:
    generation_responses = [
            json.dumps(
                {"narrations": ["这部作品总有许多温暖时刻，让人感受到平凡生活里的亲情"] * 3},
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "narrations": [
                        "第1项：《雨夜的约定》｜小新冒雨寻找走失的小白，最后在河边把它救回，因此这集以真实行动打动观众。",
                        "第2项：《爸爸住院了》｜广志受伤住院后，小新独自照顾家里并设法逗父亲开心，这份担当让它入选。",
                        "第3项：《离别的车站》｜小新追着即将离开的朋友跑到车站完成告别，具体的离别行动让这一集值得推荐。",
                    ]
                },
                ensure_ascii=False,
            ),
        ]
    fake_llm = _ControlledScreenRankingLLM(
        generation_responses,
        [
            _rejected_judge_response(3, "缺少明确条目和具体剧情"),
            _accepted_judge_response(3),
        ],
    )

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="《蜡笔小新》最感人的3集",
            n_scenes=3,
            min_words=5,
            max_words=40,
            content_recipe="ranking",
        )
    )

    assert len(fake_llm.generation_calls) == 2
    assert len(fake_llm.judge_calls) == 2
    assert "缺少明确条目" in fake_llm.generation_calls[1][0]
    assert narrations[0].startswith("第1项：")
    assert narrations[1].startswith("第2项：")
    assert narrations[2].startswith("第3项：")


def test_film_ranking_rewrites_structured_emotional_filler() -> None:
    generation_responses = [
            json.dumps(
                {
                    "narrations": [
                        "第1项：最温暖的一集｜它让我们看见平凡生活里的爱与成长"
                    ]
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "narrations": [
                        "第1项：《大人帝国的反击》｜小新为了救回被旧日记忆控制的父母，独自穿过游乐园阻止反派，这份行动和冲突让它入选。"
                    ]
                },
                ensure_ascii=False,
            ),
        ]
    fake_llm = _ControlledScreenRankingLLM(
        generation_responses,
        [
            _rejected_judge_response(1, "抽象情绪不能代替剧情事件"),
            _accepted_judge_response(1),
        ],
    )

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="《蜡笔小新》最温暖的1集",
            n_scenes=1,
            min_words=5,
            max_words=40,
            content_recipe="ranking",
        )
    )

    assert len(fake_llm.generation_calls) == 2
    assert len(fake_llm.judge_calls) == 2
    assert "抽象情绪" in fake_llm.generation_calls[1][0]
    assert "小新为了救回" in narrations[0]


@pytest.mark.parametrize(
    "generic_copy",
    [
        "第1项：《雨夜的约定》｜介绍这一集的关键剧情，以及它为什么值得推荐",
        "第1项：《雨夜的约定》｜小新很难过，这份感动让它值得推荐",
        "第1项：《雨夜的约定》｜小新面对成长，决定做出选择，所以这一集值得推荐",
        "第1项：《雨夜的约定》｜这一集的主角为了救回某人而行动，因此值得推荐",
        "第1项：《雨夜的约定》｜有人为了救回朋友，因此值得推荐",
        "第1项：《雨夜的约定》｜小新很难过，但后来决定寻找希望，所以值得推荐",
        "第1项：《雨夜的约定》｜这个故事讲述救回朋友的过程，因此值得推荐",
        "第1项：《雨夜的约定》｜这时他救回朋友，因此值得推荐",
        "第1项：《雨夜的约定》｜剧中有人寻找失物，所以值得推荐",
        "第1项：《雨夜的约定》｜为了救回朋友付出很多，因此值得推荐",
        "第1项：《感人故事》｜小新救回小白，因此值得推荐",
        "第1项：《这一段》｜小新救回小白，因此值得推荐",
        "第1项：《精彩剧集》｜小新救回小白，因此值得推荐",
        "第1项：《雨夜的约定》｜某位少年救回朋友，因此值得推荐",
        "第1项：《雨夜的约定》｜一个人寻找失物，所以值得推荐",
        "第1项：《雨夜的约定》｜朋友被救回，因此值得推荐",
        "第1项：《催泪名场面》｜小新救回小白，因此值得推荐",
        "第1项：《第一名》｜小新救回小白，因此值得推荐",
        "第1项：《未命名剧集》｜小新救回小白，因此值得推荐",
    ],
)
def test_film_ranking_rewrites_copy_without_specific_plot_evidence(
    generic_copy: str,
) -> None:
    generation_responses = [
            json.dumps({"narrations": [generic_copy]}, ensure_ascii=False),
            json.dumps(
                {
                    "narrations": [
                        "第1项：《雨夜的约定》｜小新冒雨寻找走失的小白，最后在河边把它救回，因此这段具体行动让它入选。"
                    ]
                },
                ensure_ascii=False,
            ),
        ]
    fake_llm = _ControlledScreenRankingLLM(
        generation_responses,
        [
            _rejected_judge_response(1, "缺少具体人物、行动或事件"),
            _accepted_judge_response(1),
        ],
    )

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="《蜡笔小新》最感人的1集",
            n_scenes=1,
            min_words=5,
            max_words=50,
            content_recipe="ranking",
        )
    )

    assert len(fake_llm.generation_calls) == 2
    assert len(fake_llm.judge_calls) == 2
    assert "具体人物、行动或事件" in fake_llm.generation_calls[1][0]
    assert "冒雨寻找走失的小白" in narrations[0]


def test_film_ranking_accepts_observable_plot_without_known_action_word() -> None:
    concrete_copy = (
        "第1项：《美冴的生日》｜小新攒下零花钱给美冴买了一束花，"
        "母子在厨房相拥，因此这段笨拙的祝福让它入选。"
    )
    fake_llm = _ControlledScreenRankingLLM(
        [json.dumps({"narrations": [concrete_copy]}, ensure_ascii=False)],
        [_accepted_judge_response(1)],
    )

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="《蜡笔小新》最感人的1集",
            n_scenes=1,
            min_words=5,
            max_words=50,
            content_recipe="ranking",
        )
    )

    assert len(fake_llm.generation_calls) == 1
    assert len(fake_llm.judge_calls) == 1
    assert narrations == [concrete_copy]


def test_film_ranking_rewrites_abstract_object_despite_action_word() -> None:
    abstract_copy = (
        "第1项：《雨夜的约定》｜小新寻找内心的成长，因此这一集值得推荐。"
    )
    concrete_copy = (
        "第1项：《美冴的生日》｜小新攒下零花钱给美冴买了一束花，"
        "母子在厨房相拥，因此这段笨拙的祝福让它入选。"
    )
    generation_responses = [
            json.dumps({"narrations": [abstract_copy]}, ensure_ascii=False),
            json.dumps({"narrations": [concrete_copy]}, ensure_ascii=False),
        ]
    fake_llm = _ControlledScreenRankingLLM(
        generation_responses,
        [
            _rejected_judge_response(1, "寻找内心成长不是可观察事件"),
            _accepted_judge_response(1),
        ],
    )

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="《蜡笔小新》最感人的1集",
            n_scenes=1,
            min_words=5,
            max_words=50,
            content_recipe="ranking",
        )
    )

    assert len(fake_llm.generation_calls) == 2
    assert len(fake_llm.judge_calls) == 2
    assert narrations == [concrete_copy]


def test_film_ranking_accepts_structured_plot_evidence_response() -> None:
    narration = (
        "第1项：《美冴的生日》｜美冴生日当天，小新攒下零花钱给她买了一束花，"
        "母子在厨房相拥，因此这段笨拙的祝福让它入选。"
    )
    response = {
        "narrations": [
            {
                "narration": narration,
                "item_name": "美冴的生日",
                "character": "小新和美冴",
                "situation": "美冴生日当天",
                "action_or_conflict": "小新攒下零花钱给她买了一束花，母子在厨房相拥",
                "selection_reason": "这段笨拙的祝福让它入选",
            }
        ]
    }
    fake_llm = _ControlledScreenRankingLLM(
        [json.dumps(response, ensure_ascii=False)],
        [_accepted_judge_response(1)],
    )

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="《蜡笔小新》最感人的1集",
            n_scenes=1,
            min_words=5,
            max_words=60,
            content_recipe="ranking",
        )
    )

    assert narrations == [narration]
    assert len(fake_llm.generation_calls) == 1
    assert len(fake_llm.judge_calls) == 1
    for field in (
        "item_name",
        "character",
        "situation",
        "action_or_conflict",
        "selection_reason",
    ):
        assert field in fake_llm.generation_calls[0][0]


def test_screen_judge_rejects_legacy_weather_atmosphere_and_rewrites_once() -> None:
    atmosphere = (
        "第1项：《雨夜的约定》｜雨夜里的街道格外寂静，因此这一集值得推荐"
    )
    concrete = (
        "第1项：《雨夜的约定》｜小新把唯一的雨伞递给风间，"
        "两人一起跑回家，因此这次互助让它入选"
    )
    generation_responses = iter(
        [
            json.dumps({"narrations": [atmosphere]}, ensure_ascii=False),
            json.dumps({"narrations": [concrete]}, ensure_ascii=False),
        ]
    )
    judge_responses = iter(
        [
            _judge_response(
                _judge_item(
                    1,
                    identifiable_character=False,
                    observable_action=False,
                    event_supported_reason=False,
                    issues=["只有天气氛围，没有可识别人物或具体事件"],
                )
            ),
            _judge_response(_judge_item(1)),
        ]
    )
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_llm(*, prompt: str, **kwargs) -> str:
        calls.append((prompt, kwargs))
        if _SCREEN_JUDGE_MARKER in prompt:
            return next(judge_responses)
        return next(generation_responses)

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="《蜡笔小新》最感人的1集",
            n_scenes=1,
            min_words=5,
            max_words=50,
            content_recipe="ranking",
        )
    )

    generation_calls = [call for call in calls if _SCREEN_JUDGE_MARKER not in call[0]]
    judge_calls = [call for call in calls if _SCREEN_JUDGE_MARKER in call[0]]
    assert narrations == [concrete]
    assert len(generation_calls) == 2
    assert len(judge_calls) == 2
    assert "只有天气氛围" in generation_calls[1][0]


def test_screen_judge_rejects_structured_dream_direction() -> None:
    abstract_narration = (
        "第1项：《雨夜的约定》｜雨夜里，小新追寻梦想的方向，"
        "因此这段成长让它入选"
    )
    concrete_narration = (
        "第1项：《雨夜的约定》｜雨夜里，小新把唯一的雨伞递给风间，"
        "因此这次互助让它入选"
    )
    generation_responses = iter(
        [
            json.dumps(
                {
                    "narrations": [
                        {
                            "narration": abstract_narration,
                            "item_name": "雨夜的约定",
                            "character": "小新",
                            "situation": "雨夜里",
                            "action_or_conflict": "小新追寻梦想的方向",
                            "selection_reason": "这段成长让它入选",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "narrations": [
                        {
                            "narration": concrete_narration,
                            "item_name": "雨夜的约定",
                            "character": "小新和风间",
                            "situation": "雨夜里",
                            "action_or_conflict": "小新把唯一的雨伞递给风间",
                            "selection_reason": "这次互助让它入选",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
        ]
    )
    judge_responses = iter(
        [
            _judge_response(
                _judge_item(
                    1,
                    observable_action=False,
                    event_supported_reason=False,
                    issues=["追寻梦想是抽象目标，不是镜头可见的具体事件"],
                )
            ),
            _judge_response(_judge_item(1)),
        ]
    )
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_llm(*, prompt: str, **kwargs) -> str:
        calls.append((prompt, kwargs))
        if _SCREEN_JUDGE_MARKER in prompt:
            return next(judge_responses)
        return next(generation_responses)

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="《蜡笔小新》最感人的1集",
            n_scenes=1,
            min_words=5,
            max_words=50,
            content_recipe="ranking",
        )
    )

    generation_calls = [call for call in calls if _SCREEN_JUDGE_MARKER not in call[0]]
    judge_calls = [call for call in calls if _SCREEN_JUDGE_MARKER in call[0]]
    assert narrations == [concrete_narration]
    assert len(generation_calls) == 2
    assert len(judge_calls) == 2
    assert "追寻梦想" in generation_calls[1][0]


def test_screen_judge_accepts_observable_choice_to_hand_over_umbrella() -> None:
    narration = (
        "第1项：《雨夜的约定》｜放学突遇大雨，小新选择把唯一的雨伞递给风间，"
        "因此这次互助让它入选"
    )
    generation_response = json.dumps(
        {
            "narrations": [
                {
                    "narration": narration,
                    "item_name": "雨夜的约定",
                    "character": "小新和风间",
                    "situation": "放学突遇大雨",
                    "action_or_conflict": "小新选择把唯一的雨伞递给风间",
                    "selection_reason": "这次互助让它入选",
                }
            ]
        },
        ensure_ascii=False,
    )
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_llm(*, prompt: str, **kwargs) -> str:
        calls.append((prompt, kwargs))
        if _SCREEN_JUDGE_MARKER in prompt:
            return _judge_response(_judge_item(1))
        return generation_response

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="《蜡笔小新》最感人的1集",
            n_scenes=1,
            min_words=5,
            max_words=50,
            content_recipe="ranking",
        )
    )

    generation_calls = [call for call in calls if _SCREEN_JUDGE_MARKER not in call[0]]
    judge_calls = [call for call in calls if _SCREEN_JUDGE_MARKER in call[0]]
    assert narrations == [narration]
    assert len(generation_calls) == 1
    assert len(judge_calls) == 1
    assert judge_calls[0][1]["temperature"] == 0


def test_screen_judge_validates_all_items_in_one_batch_call() -> None:
    narrations_input = [
        "第1项：《雨夜的约定》｜小新把雨伞递给风间，因此这次互助让它入选",
        "第2项：《美冴的生日》｜小新攒钱给美冴买花，因此这份祝福让它入选",
    ]
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_llm(*, prompt: str, **kwargs) -> str:
        calls.append((prompt, kwargs))
        if _SCREEN_JUDGE_MARKER in prompt:
            return _judge_response(_judge_item(1), _judge_item(2))
        return json.dumps({"narrations": narrations_input}, ensure_ascii=False)

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="《蜡笔小新》最感人的2集",
            n_scenes=2,
            min_words=5,
            max_words=50,
            content_recipe="ranking",
        )
    )

    judge_calls = [call for call in calls if _SCREEN_JUDGE_MARKER in call[0]]
    assert narrations == narrations_input
    assert len(judge_calls) == 1
    assert judge_calls[0][1]["temperature"] == 0
    assert all(narration in judge_calls[0][0] for narration in narrations_input)


def test_invalid_screen_judge_response_fails_after_one_rewrite() -> None:
    narration = (
        "第1项：《雨夜的约定》｜小新把唯一的雨伞递给风间，"
        "因此这次互助让它入选"
    )
    generation_response = json.dumps({"narrations": [narration]}, ensure_ascii=False)
    judge_responses = iter(
        ["", f"```json\n{_accepted_judge_response(1)}\n```"]
    )
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_llm(*, prompt: str, **kwargs) -> str:
        calls.append((prompt, kwargs))
        if _SCREEN_JUDGE_MARKER in prompt:
            return next(judge_responses)
        return generation_response

    with pytest.raises(ValueError, match="影视盘点语义校验响应无效"):
        asyncio.run(
            generate_narrations_from_topic(
                fake_llm,
                topic="《蜡笔小新》最感人的1集",
                n_scenes=1,
                min_words=5,
                max_words=50,
                content_recipe="ranking",
            )
        )

    generation_calls = [call for call in calls if _SCREEN_JUDGE_MARKER not in call[0]]
    judge_calls = [call for call in calls if _SCREEN_JUDGE_MARKER in call[0]]
    assert len(generation_calls) == 2
    assert len(judge_calls) == 2


def test_screen_judge_true_flags_with_issues_cannot_fail_open() -> None:
    narration = (
        "第1项：《雨夜的约定》｜小新把唯一的雨伞递给风间，"
        "因此这次互助让它入选"
    )
    generation_response = json.dumps({"narrations": [narration]}, ensure_ascii=False)
    contradictory = _judge_item(1, issues=["行动对象仍不明确"])
    judge_responses = iter(
        [_judge_response(contradictory), _accepted_judge_response(1)]
    )
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_llm(*, prompt: str, **kwargs) -> str:
        calls.append((prompt, kwargs))
        if _SCREEN_JUDGE_MARKER in prompt:
            return next(judge_responses)
        return generation_response

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="《蜡笔小新》最感人的1集",
            n_scenes=1,
            min_words=5,
            max_words=50,
            content_recipe="ranking",
        )
    )

    generation_calls = [call for call in calls if _SCREEN_JUDGE_MARKER not in call[0]]
    judge_calls = [call for call in calls if _SCREEN_JUDGE_MARKER in call[0]]
    assert narrations == [narration]
    assert len(generation_calls) == 2
    assert len(judge_calls) == 2


def test_tool_ranking_with_collection_word_does_not_use_film_copy_guardrail() -> None:
    responses = iter(
        [
            json.dumps(
                {
                    "narrations": [
                        "第1项：文献管理器｜温暖的体验使资料收集更轻松，也陪伴用户成长"
                    ]
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "narrations": [
                        "第1项：文献管理器｜它能自动整理资料，适合需要统一管理引用的研究者。"
                    ]
                },
                ensure_ascii=False,
            ),
        ]
    )
    prompts: list[str] = []

    async def fake_llm(*, prompt: str, **_kwargs) -> str:
        prompts.append(prompt)
        return next(responses)

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="推荐10个资料收集工具",
            n_scenes=1,
            min_words=5,
            max_words=40,
            content_recipe="ranking",
        )
    )

    assert len(prompts) == 1
    assert "action_or_conflict" not in prompts[0]
    assert "资料收集" in narrations[0]


def test_movie_editing_tool_ranking_does_not_use_screen_story_schema() -> None:
    copy = (
        "第1项：《剪映》｜它支持自动字幕和多轨剪辑，因此适合快速完成电影片段制作"
    )
    prompts: list[str] = []

    async def fake_llm(*, prompt: str, **_kwargs) -> str:
        prompts.append(prompt)
        return json.dumps({"narrations": [copy]}, ensure_ascii=False)

    narrations = asyncio.run(
        generate_narrations_from_topic(
            fake_llm,
            topic="推荐1个电影剪辑工具",
            n_scenes=1,
            min_words=5,
            max_words=50,
            content_recipe="ranking",
        )
    )

    assert narrations == [copy]
    assert len(prompts) == 1
    assert "action_or_conflict" not in prompts[0]


def test_topic_generation_strict_count_rejects_excess_narrations() -> None:
    async def fake_llm(**_kwargs) -> str:
        return json.dumps({"narrations": ["旁白一", "旁白二", "多余旁白"]}, ensure_ascii=False)

    with pytest.raises(ValueError, match="需要 2 条，实际 3 条"):
        asyncio.run(
            generate_narrations_from_topic(
                fake_llm,
                topic="普通主题",
                n_scenes=2,
                min_words=2,
                max_words=20,
                strict_count=True,
            )
        )


def test_document_generation_strict_count_rejects_excess_narrations() -> None:
    async def fake_llm(**_kwargs) -> str:
        return json.dumps({"narrations": ["旁白一", "旁白二", "多余旁白"]}, ensure_ascii=False)

    with pytest.raises(ValueError, match="需要 2 条，实际 3 条"):
        asyncio.run(
            generate_narrations_from_content(
                fake_llm,
                content="文档正文",
                n_scenes=2,
                min_words=2,
                max_words=20,
                strict_count=True,
            )
        )
