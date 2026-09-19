from morpheus_video_studio.utils.content_generators import clean_narration


def test_literal_backslash_n_stripped():
    # LLM 双转义 JSON 产生的字面 \n(两个字符),会印到字幕上
    assert clean_narration("打开首页\\n看到介绍") == "打开首页 看到介绍"


def test_real_newlines_collapsed():
    # 真换行(存档里真实出现过的形态)
    assert clean_narration("打开首页\n看到介绍\n\n想找教会") == "打开首页 看到介绍 想找教会"


def test_tabs_and_literal_variants():
    assert clean_narration("第一\t第二") == "第一 第二"
    assert clean_narration("甲\\t乙\\r丙") == "甲 乙 丙"


def test_clean_text_untouched():
    s = "当归，气味甘温无毒，主咳逆上气。"
    assert clean_narration(s) == s


def test_empty_safe():
    assert clean_narration("") == ""
    assert clean_narration("   \n  ") == ""
