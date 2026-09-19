from morpheus_video_studio.prompts import build_topic_narration_prompt
from morpheus_video_studio.prompts.content_recipes import (
    get_content_recipe,
    get_recipe_block,
    list_content_recipes,
    resolve_content_recipe,
)


def test_recipe_registry_uses_eight_general_topics() -> None:
    recipes = list_content_recipes()
    assert [item["id"] for item in recipes] == [
        "general",
        "science",
        "story",
        "history",
        "tutorial",
        "commentary",
        "ranking",
        "health",
    ]
    assert [item["label"] for item in recipes] == [
        "自由创作",
        "知识科普",
        "故事讲述",
        "历史人文",
        "实用教程",
        "观点评论",
        "盘点推荐",
        "健康生活",
    ]


def test_health_recipe_keeps_medical_safety_boundaries() -> None:
    block = get_content_recipe("health")["block"]
    assert "不能替代专业诊疗" in block
    assert "不得夸大疗效" in block
    assert "及时就医" in block


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
        recipe_block=get_recipe_block("health"),
    )
    assert "栏目配方：健康生活" in prompt
    assert prompt.index("当归的功效") < prompt.index("栏目配方：健康生活") < prompt.index("# Output Requirements")


def test_prompt_without_recipe_is_unchanged_shape() -> None:
    prompt = build_topic_narration_prompt(
        topic="test topic", n_storyboard=3, min_words=5, max_words=20
    )
    assert "栏目配方" not in prompt
    assert "test topic" in prompt


def test_topic_prompt_defines_chinese_length_in_characters() -> None:
    prompt = build_topic_narration_prompt(
        topic="小新搞笑片段", n_storyboard=5, min_words=18, max_words=30
    )

    assert "中文每段 18～30 个汉字" in prompt
    assert "不得少于 18 个汉字" in prompt


def test_knowledge_recipes_forbid_human_figures() -> None:
    """本地 SD1.5 画人严重变形,知识类栏目一律回避人物。"""
    from morpheus_video_studio.prompts.content_recipes import get_recipe_visual_rules
    for rid in ("science", "history", "health"):
        rules = get_recipe_visual_rules(rid)
        assert "严禁出现人物" in rules, f"{rid} 缺少禁人物规则"
        assert "器物" in rules or "图表" in rules
    # 通用栏目不加限制
    assert get_recipe_visual_rules("general") == ""
    assert get_recipe_visual_rules(None) == ""


def test_visual_rules_reach_the_image_prompt() -> None:
    from morpheus_video_studio.prompts import build_image_prompt_prompt
    from morpheus_video_studio.prompts.content_recipes import get_recipe_visual_rules
    with_rules = build_image_prompt_prompt(
        ["当归性温味甘"], 30, 60, visual_rules=get_recipe_visual_rules("health")
    )
    without = build_image_prompt_prompt(["当归性温味甘"], 30, 60)
    assert "严禁出现人物" in with_rules
    assert "严禁出现人物" not in without


def test_visual_rules_reach_the_video_prompt() -> None:
    from morpheus_video_studio.prompts.video_generation import build_video_prompt_prompt

    prompt = build_video_prompt_prompt(
        ["当归性温味甘"], 30, 60, visual_rules="严禁出现人物，优先器物"
    )

    assert "严禁出现人物，优先器物" in prompt


def test_each_structured_topic_has_a_distinct_recipe_block() -> None:
    for recipe_id in ("science", "story", "history", "tutorial", "commentary", "ranking", "health"):
        block = get_recipe_block(recipe_id)
        assert "栏目配方" in block
        assert "结构骨架" in block


def test_ranking_intent_is_detected_from_numbered_topic() -> None:
    assert resolve_content_recipe("《蜡笔小新》最感人的5集", "general") == "ranking"
    assert resolve_content_recipe("盘点最值得看的十部电影", "general") == "ranking"
    assert resolve_content_recipe("Top 8 productivity apps", "general") == "ranking"


def test_explicit_structured_recipe_is_not_overridden() -> None:
    assert resolve_content_recipe("最重要的5个健康习惯", "health") == "health"


def test_ranking_recipe_uses_every_scene_for_one_named_item() -> None:
    block = get_recipe_block("ranking")
    assert "每个分镜直接介绍一个条目" in block
    assert "不要占用单独分镜做开场或总结" in block
    assert "第1项：具体名称｜" in block


def test_ranking_recipe_demands_film_explanation_not_emotional_filler() -> None:
    block = get_recipe_block("ranking")
    for requirement in ("具体人物", "人物行动", "剧情冲突", "关键场面", "入选理由"):
        assert requirement in block
    assert "不能用抽象情绪或人生感悟代替剧情介绍" in block
