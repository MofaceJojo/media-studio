from morpheus_video_studio.prompts.content_recipes import (
    get_content_recipe,
    get_recipe_block,
    list_content_recipes,
)
from morpheus_video_studio.prompts import build_topic_narration_prompt


def test_recipe_registry_covers_planned_verticals() -> None:
    ids = {recipe["id"] for recipe in list_content_recipes()}
    assert {"general", "science", "tcm", "ranking", "medical"} <= ids


def test_safety_critical_recipes_include_disclaimers() -> None:
    assert "遵医嘱" in get_content_recipe("tcm")["block"]
    assert "不能替代专业诊疗" in get_content_recipe("medical")["block"]
    # 不夸大疗效是两个医疗类栏目的硬性禁忌
    assert "不得夸大疗效" in get_content_recipe("tcm")["block"]
    assert "不承诺疗效" in get_content_recipe("medical")["block"]


def test_unknown_or_empty_recipe_returns_no_overlay() -> None:
    assert get_recipe_block(None) == ""
    assert get_recipe_block("") == ""
    assert get_recipe_block("does-not-exist") == ""
    assert get_recipe_block("general") == ""


def test_prompt_injects_recipe_block_between_topic_and_requirements() -> None:
    prompt = build_topic_narration_prompt(
        topic="当归的功效",
        n_storyboard=5,
        min_words=15,
        max_words=40,
        recipe_block=get_recipe_block("tcm"),
    )
    assert "栏目配方：中药百科" in prompt
    assert prompt.index("当归的功效") < prompt.index("栏目配方：中药百科") < prompt.index("# Output Requirements")


def test_prompt_without_recipe_is_unchanged_shape() -> None:
    prompt = build_topic_narration_prompt(
        topic="test topic", n_storyboard=3, min_words=5, max_words=20
    )
    assert "栏目配方" not in prompt
    assert "test topic" in prompt
