# Persistent Tool Drawer Trigger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the left tool drawer discoverable at all times with a visible menu/reopen control, clear collapse control, and semantic icons for every management entry.

**Architecture:** Keep Streamlit's native sidebar state and controls, then style the stable `stSidebarCollapsedControl` and `stSidebarCollapseButton` test IDs instead of introducing JavaScript state. Keep navigation metadata in `web/navigation.py` as the single source of truth and render icons through `st.page_link`.

**Tech Stack:** Python 3.13, Streamlit, CSS injected by `web/components/studio_shell.py`, pytest, in-app browser verification.

## Global Constraints

- The menu trigger must remain visible after the overlay sidebar closes.
- The sidebar remains expanded on first open and respects manual collapse afterward.
- The main workbench gains no new permanent module.
- Reuse Streamlit native controls; do not add a second sidebar state system.
- Minimum visible trigger size is 40 pixels.

---

### Task 1: Add semantic navigation icons

**Files:**
- Modify: `web/navigation.py`
- Modify: `tests/test_web_navigation.py`

**Interfaces:**
- Consumes: `CORE_PAGE_SPECS` and `TOOL_PAGE_SPECS` navigation metadata.
- Produces: each drawer spec exposes an `icon: str`; `render_tool_drawer()` passes it to `st.page_link`.

- [ ] **Step 1: Write the failing test**

```python
def test_tool_drawer_entries_have_semantic_icons() -> None:
    assert CORE_PAGE_SPECS[0]["icon"] == "🏠"
    assert [item["icon"] for item in TOOL_PAGE_SPECS] == ["🗃️", "🎞️", "⚙️"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Volumes/MACDATA/morpheus-video-studio/.venv/bin/python -m pytest -q tests/test_web_navigation.py`

Expected: FAIL because the specs do not yet contain `icon`.

- [ ] **Step 3: Add icons to metadata and page links**

```python
CORE_PAGE_SPECS = (
    {"path": "pages/1_🏠_Studio.py", "label": "工作台", "icon": "🏠", "default": True},
    {"path": "pages/2_📚_Content_Library.py", "label": "内容创作", "icon": "📝"},
    {"path": "pages/3_🎙️_Audio_Workshop.py", "label": "音频创作", "icon": "🎙️"},
    {"path": "pages/4_🎬_Video_Workshop.py", "label": "视频创作", "icon": "🎬"},
    {"path": "pages/5_🤖_Digital_Human.py", "label": "数字人口播", "icon": "🤖"},
)

TOOL_PAGE_SPECS = (
    {"path": "pages/6_🗂️_Asset_Library.py", "label": "已有资产", "icon": "🗃️"},
    {"path": "pages/2_📚_History.py", "label": "视频项目", "icon": "🎞️"},
    {"path": "pages/7_⚙️_Settings.py", "label": "系统设置", "icon": "⚙️"},
)

st.page_link(path, label=label, icon=icon)
```

All existing core specs receive an icon value accepted by `st.Page`; `build_streamlit_pages()` passes `icon=str(spec["icon"])` into `st.Page`, and the drawer renders `🏠`, `🗃️`, `🎞️`, and `⚙️` next to their current labels.

- [ ] **Step 4: Run navigation tests**

Run: `/Volumes/MACDATA/morpheus-video-studio/.venv/bin/python -m pytest -q tests/test_web_navigation.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/navigation.py tests/test_web_navigation.py
git commit -m "feat: add tool drawer navigation icons"
```

### Task 2: Make native open and close controls persistent and obvious

**Files:**
- Modify: `web/components/studio_shell.py`
- Modify: `tests/test_sidebar_visibility.py`

**Interfaces:**
- Consumes: Streamlit native `data-testid="stSidebarCollapsedControl"` and `data-testid="stSidebarCollapseButton"` elements.
- Produces: a fixed `☰ 菜单` collapsed trigger and a visible `‹ 收起` expanded control without custom JavaScript state.

- [ ] **Step 1: Write the failing style contract tests**

```python
def test_sidebar_controls_have_persistent_labels_and_minimum_size() -> None:
    assert 'data-testid="stSidebarCollapsedControl"' in SHELL_SOURCE
    assert 'content: "菜单"' in SHELL_SOURCE
    assert 'data-testid="stSidebarCollapseButton"' in SHELL_SOURCE
    assert 'content: "收起"' in SHELL_SOURCE
    assert "min-height: 40px" in SHELL_SOURCE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Volumes/MACDATA/morpheus-video-studio/.venv/bin/python -m pytest -q tests/test_sidebar_visibility.py`

Expected: FAIL because the native controls have no visible text styling.

- [ ] **Step 3: Style the native controls**

Add CSS scoped to the two Streamlit test IDs:

```css
[data-testid="stSidebarCollapsedControl"] {
  position: fixed;
  top: 10px;
  left: 12px;
  z-index: 1000000;
}
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="stSidebarCollapseButton"] button {
  min-width: 40px;
  min-height: 40px;
  border-radius: 10px;
  font-weight: 700;
}
[data-testid="stSidebarCollapsedControl"] button::after {
  content: "菜单";
  margin-left: 6px;
}
[data-testid="stSidebarCollapseButton"] button::after {
  content: "收起";
  margin-left: 4px;
}
```

Use the existing navy/white design tokens, add hover and focus-visible states, and ensure the expanded control remains legible on the navy sidebar.

- [ ] **Step 4: Run sidebar tests**

Run: `/Volumes/MACDATA/morpheus-video-studio/.venv/bin/python -m pytest -q tests/test_sidebar_visibility.py`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/components/studio_shell.py tests/test_sidebar_visibility.py
git commit -m "fix: keep sidebar menu control discoverable"
```

### Task 3: Full regression and browser acceptance

**Files:**
- Verify: `web/app.py`
- Verify: `web/navigation.py`
- Verify: `web/components/studio_shell.py`

**Interfaces:**
- Consumes: completed drawer metadata and CSS control contracts.
- Produces: verified user-facing sidebar behavior at `http://127.0.0.1:18501/Video_Workshop`.

- [ ] **Step 1: Run the complete automated suite**

Run: `/Volumes/MACDATA/morpheus-video-studio/.venv/bin/python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Run static verification**

Run: `/Volumes/MACDATA/morpheus-video-studio/.venv/bin/python -m compileall -q web morpheus_video_studio tests && git diff --check`

Expected: exit code 0 and no output.

- [ ] **Step 3: Verify the open/collapse/reopen flow in the browser**

At the current in-app browser viewport:

1. Reload `/Video_Workshop` and confirm the sidebar is initially visible.
2. Confirm `🏠 返回工作台`, `🗃️ 已有资产`, `🎞️ 视频项目`, and `⚙️ 系统设置` are readable.
3. Click the unique native `stSidebarCollapseButton` and confirm the sidebar closes.
4. Confirm the fixed `☰ 菜单` control remains visible.
5. Click the unique native `stSidebarCollapsedControl` and confirm the sidebar reopens.
6. Keep the corrected page visible for user review.

- [ ] **Step 4: Record the completed state**

Run: `git status --short && git log -3 --oneline`

Expected: clean worktree and both implementation commits visible.
