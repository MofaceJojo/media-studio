from pathlib import Path


STUDIO_SOURCE = (
    Path(__file__).resolve().parents[1] / "web" / "pages" / "1_🏠_Studio.py"
).read_text(encoding="utf-8")


def test_studio_home_only_renders_four_core_actions() -> None:
    assert STUDIO_SOURCE.count("render_core_action(") == 4
    for path in (
        "pages/2_📚_Content_Library.py",
        "pages/3_🎙️_Audio_Workshop.py",
        "pages/4_🎬_Video_Workshop.py",
        "pages/5_🤖_Digital_Human.py",
    ):
        assert path in STUDIO_SOURCE


def test_studio_home_does_not_repeat_tool_drawer_content() -> None:
    assert "render_metric_cards(" not in STUDIO_SOURCE
    assert "render_workspace_context(" not in STUDIO_SOURCE
    assert "pages/6_🗂️_Asset_Library.py" not in STUDIO_SOURCE
    assert "pages/7_⚙️_Settings.py" not in STUDIO_SOURCE
