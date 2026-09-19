from web.navigation import CORE_PAGE_SPECS, TOOL_PAGE_SPECS


def test_navigation_separates_core_pages_from_tools() -> None:
    assert [item["label"] for item in CORE_PAGE_SPECS] == [
        "工作台",
        "内容创作",
        "音频创作",
        "视频创作",
        "数字人口播",
    ]
    assert [item["label"] for item in TOOL_PAGE_SPECS] == [
        "已有资产",
        "视频项目",
        "系统设置",
    ]


def test_tool_drawer_contains_no_core_creation_modules() -> None:
    tool_paths = {item["path"] for item in TOOL_PAGE_SPECS}
    assert "pages/2_📚_Content_Library.py" not in tool_paths
    assert "pages/3_🎙️_Audio_Workshop.py" not in tool_paths
    assert "pages/4_🎬_Video_Workshop.py" not in tool_paths
    assert "pages/5_🤖_Digital_Human.py" not in tool_paths


def test_tool_drawer_entries_have_semantic_icons() -> None:
    assert CORE_PAGE_SPECS[0]["icon"] == "🏠"
    assert [item["icon"] for item in TOOL_PAGE_SPECS] == ["🗃️", "🎞️", "⚙️"]
