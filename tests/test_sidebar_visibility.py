from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "web" / "app.py").read_text(encoding="utf-8")
SHELL_SOURCE = (ROOT / "web" / "components" / "studio_shell.py").read_text(encoding="utf-8")


def test_tool_drawer_is_visible_on_first_open() -> None:
    assert 'initial_sidebar_state="expanded"' in APP_SOURCE


def test_collapsed_drawer_keeps_a_visible_reopen_control() -> None:
    assert 'header[data-testid="stHeader"] {\n          display: none;' not in SHELL_SOURCE
    assert 'header[data-testid="stHeader"]' in SHELL_SOURCE
    assert "background: transparent" in SHELL_SOURCE


def test_sidebar_page_links_remain_readable_on_dark_background() -> None:
    assert 'section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]' in SHELL_SOURCE
    assert "background: rgba(255, 255, 255, 0.08)" in SHELL_SOURCE


def test_sidebar_controls_have_persistent_labels_and_minimum_size() -> None:
    assert 'data-testid="stSidebarCollapsedControl"' in SHELL_SOURCE
    assert 'content: "菜单"' in SHELL_SOURCE
    assert 'data-testid="stSidebarCollapseButton"' in SHELL_SOURCE
    assert 'content: "收起"' in SHELL_SOURCE
    assert "min-height: 40px" in SHELL_SOURCE
    assert "visibility: visible !important" in SHELL_SOURCE


def test_collapsed_sidebar_repositions_its_native_button_into_view() -> None:
    assert 'section[data-testid="stSidebar"][aria-expanded="false"]' in SHELL_SOURCE
    assert "transform: translateX(300px)" in SHELL_SOURCE
    assert "overflow: visible !important" in SHELL_SOURCE
