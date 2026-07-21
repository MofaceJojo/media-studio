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


def test_knowledge_recipes_forbid_human_figures() -> None:
    """本地 SD1.5 画人严重变形,知识类栏目一律回避人物。"""
    from morpheus_video_studio.prompts.content_recipes import get_recipe_visual_rules
    for rid in ("tcm", "science", "medical"):
        rules = get_recipe_visual_rules(rid)
        assert "严禁出现人物" in rules, f"{rid} 缺少禁人物规则"
        assert "药材" in rules or "器物" in rules  # 给出替代题材
    # 通用栏目不加限制
    assert get_recipe_visual_rules("general") == ""
    assert get_recipe_visual_rules(None) == ""


def test_visual_rules_reach_the_image_prompt() -> None:
    from morpheus_video_studio.prompts import build_image_prompt_prompt
    from morpheus_video_studio.prompts.content_recipes import get_recipe_visual_rules
    with_rules = build_image_prompt_prompt(
        ["当归性温味甘"], 30, 60, visual_rules=get_recipe_visual_rules("tcm")
    )
    without = build_image_prompt_prompt(["当归性温味甘"], 30, 60)
    assert "严禁出现人物" in with_rules
    assert "严禁出现人物" not in without


def test_tcm_recipe_grades_evidence() -> None:
    """古方新证的立身之本:传统记载与现代证据必须分开表述。"""
    block = get_content_recipe("tcm")["block"]
    assert "证据分级" in block
    assert "古人认为" in block and "现代研究" in block
