# 核心工作台、工具抽屉与通用栏目实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把首页收敛为四个核心创作入口，把资产、视频项目和系统设置移入默认收起的工具边栏，同时扩展通用内容栏目并修复短主题把 5 个分镜压成 1 个的问题。

**Architecture:** 使用 Streamlit 的隐藏页面导航注册全部现有页面，再用自定义侧栏只呈现工作台返回入口和三个低频工具入口。首页只读取最近一个视频项目并渲染四个核心模块。栏目配方继续由集中注册表驱动；分镜目标通过一个纯函数区分主题、文档和固定文案模式，便于测试。

**Tech Stack:** Python 3.11+、Streamlit、pytest、现有 CSS 设计令牌。

## Global Constraints

- 不删除现有页面、生成流程、配置字段或用户数据。
- 不引入新的前端框架、图标库或第三方依赖。
- 左侧边栏默认收起。
- 首页只突出内容、音频、视频和数字人口播。
- 主题创作必须尊重用户选择的目标分镜数。
- 健康生活栏目必须保留医疗安全边界。

---

### Task 1: 隐藏主导航并建立工具抽屉

**Files:**
- Create: `web/navigation.py`
- Modify: `web/app.py`
- Test: `tests/test_web_navigation.py`

**Interfaces:**
- Produces: `CORE_PAGE_SPECS`、`TOOL_PAGE_SPECS`、`build_streamlit_pages()`、`render_tool_drawer()`
- Consumes: Streamlit `st.Page`、`st.navigation`、`st.sidebar.page_link`

- [ ] **Step 1: Write the failing test**

```python
from web.navigation import CORE_PAGE_SPECS, TOOL_PAGE_SPECS


def test_navigation_separates_core_pages_from_tools() -> None:
    assert [item["label"] for item in CORE_PAGE_SPECS] == [
        "工作台", "内容创作", "音频创作", "视频创作", "数字人口播"
    ]
    assert [item["label"] for item in TOOL_PAGE_SPECS] == [
        "已有资产", "视频项目", "系统设置"
    ]


def test_tool_drawer_contains_no_core_creation_modules() -> None:
    tool_paths = {item["path"] for item in TOOL_PAGE_SPECS}
    assert "pages/2_📚_Content_Library.py" not in tool_paths
    assert "pages/4_🎬_Video_Workshop.py" not in tool_paths
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_web_navigation.py -q`

Expected: FAIL because `web.navigation` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create immutable page specifications, build all `st.Page` objects from them, call:

```python
pg = st.navigation(all_pages, position="hidden")
render_tool_drawer()
pg.run()
```

The drawer renders a compact “返回工作台” link followed by only “已有资产”“视频项目”“系统设置”. Keep `initial_sidebar_state="collapsed"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_web_navigation.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/navigation.py web/app.py tests/test_web_navigation.py
git commit -m "feat: separate core navigation from tool drawer"
```

### Task 2: 收敛 Studio 首页

**Files:**
- Modify: `web/pages/1_🏠_Studio.py`
- Modify: `web/components/studio_shell.py`
- Test: `tests/test_studio_home_structure.py`

**Interfaces:**
- Consumes: `StudioLibraryService.list_video_assets()` and existing `st.page_link`
- Produces: four core module links and one recent-work section

- [ ] **Step 1: Write the failing test**

Read the Studio source as UTF-8 and assert:

```python
assert source.count("render_core_action") == 4
assert "render_metric_cards(" not in source
assert "render_workspace_context(" not in source
assert "pages/6_🗂️_Asset_Library.py" not in source
assert "pages/7_⚙️_Settings.py" not in source
```

Also assert the four page paths for Content Library, Audio Workshop, Video Workshop and Digital Human are present.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_studio_home_structure.py -q`

Expected: FAIL because the current home repeats metrics, settings and asset cards.

- [ ] **Step 3: Write minimal implementation**

Add `render_core_action(title, description, path, eyebrow)` to `studio_shell.py`. Replace the existing home with:

- a short left-aligned hero;
- a two-column grid containing four `render_core_action` calls;
- a “继续创作” section showing the newest video asset, or a concise empty state linking to Video Workshop.

Do not render asset totals, workspace context, full recent lists, Settings or Asset Library on the home page.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_studio_home_structure.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/pages/1_🏠_Studio.py web/components/studio_shell.py tests/test_studio_home_structure.py
git commit -m "feat: simplify studio home around core creation"
```

### Task 3: 用八类通用题材替换混合栏目

**Files:**
- Modify: `morpheus_video_studio/prompts/content_recipes.py`
- Modify: `web/components/content_input.py`
- Modify: `tests/test_content_recipes.py`

**Interfaces:**
- Produces recipe IDs: `general`, `science`, `story`, `history`, `tutorial`, `commentary`, `ranking`, `health`
- Preserves: `get_content_recipe()`、`get_recipe_block()`、`get_recipe_visual_rules()`

- [ ] **Step 1: Write the failing tests**

```python
def test_recipe_registry_uses_eight_general_topics() -> None:
    recipes = list_content_recipes()
    assert [item["id"] for item in recipes] == [
        "general", "science", "story", "history",
        "tutorial", "commentary", "ranking", "health",
    ]
    assert [item["label"] for item in recipes] == [
        "自由创作", "知识科普", "故事讲述", "历史人文",
        "实用教程", "观点评论", "盘点推荐", "健康生活",
    ]


def test_health_recipe_keeps_medical_safety_boundaries() -> None:
    block = get_content_recipe("health")["block"]
    assert "不能替代专业诊疗" in block
    assert "不得夸大疗效" in block
    assert "及时就医" in block
```

Update visual-rule tests to cover `science`, `history` and `health` where applicable, and remove assertions for retired IDs `tcm` and `medical`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_content_recipes.py -q`

Expected: FAIL because the registry still contains `tcm` and `medical`.

- [ ] **Step 3: Implement the eight recipes**

Keep `general` empty. Give each new recipe a concise structural block:

- story: conflict → development → turn → ending;
- history: context → event → cause/effect → present meaning;
- tutorial: outcome → prerequisites → ordered steps → pitfalls → recap;
- commentary: claim → evidence → counterpoint → conclusion;
- health: phenomenon → mechanism → practical advice → warning signs → disclaimer.

Rename ranking to “盘点推荐”. Update the UI help text to describe broad topics rather than vertical channels.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_content_recipes.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add morpheus_video_studio/prompts/content_recipes.py web/components/content_input.py tests/test_content_recipes.py
git commit -m "feat: broaden video content topics"
```

### Task 4: 修复短主题错误压缩分镜数

**Files:**
- Modify: `web/components/content_input.py`
- Create: `tests/test_content_input_scene_count.py`

**Interfaces:**
- Produces: `resolve_effective_scene_count(mode: str, selected_scenes: int, planning: dict | None) -> int`
- Consumes: `estimate_scene_plan()` output for document/fixed modes only

- [ ] **Step 1: Write the failing tests**

```python
from web.components.content_input import resolve_effective_scene_count


def test_topic_mode_respects_selected_scene_count_for_short_topic() -> None:
    planning = {"recommended_scenes": 1}
    assert resolve_effective_scene_count("generate", 5, planning) == 5


def test_document_mode_can_use_length_based_scene_count() -> None:
    planning = {"recommended_scenes": 12}
    assert resolve_effective_scene_count("document", 5, planning) == 12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_content_input_scene_count.py -q`

Expected: FAIL because the helper does not exist.

- [ ] **Step 3: Implement and wire the helper**

```python
def resolve_effective_scene_count(
    mode: str, selected_scenes: int, planning: dict | None
) -> int:
    if mode == "document" and planning:
        return int(planning["recommended_scenes"])
    return int(selected_scenes)
```

In topic generation, keep the selected slider value even when auto-estimation is checked. Show length-based auto-estimation only for document mode. After a draft exists, show its estimated duration as advisory text without changing the target count.

- [ ] **Step 4: Run focused and related tests**

Run:

```bash
uv run pytest tests/test_content_input_scene_count.py tests/test_content_generators_planning.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/components/content_input.py tests/test_content_input_scene_count.py
git commit -m "fix: preserve scene target for short topics"
```

### Task 5: 全量验证与浏览器验收

**Files:**
- Modify only if verification exposes a defect.

**Interfaces:**
- Consumes all prior tasks.
- Produces a running preview at `http://127.0.0.1:18501/`.

- [ ] **Step 1: Run static and test verification**

Run:

```bash
uv run python -m compileall -q morpheus_video_studio api web
uv run pytest -q
git diff --check
```

Expected: compile exit 0, all tests pass, no whitespace errors.

- [ ] **Step 2: Reload the existing Streamlit preview**

Confirm `/_stcore/health` returns `ok`. Reload the in-app browser tab after Streamlit hot reload.

- [ ] **Step 3: Verify visible behavior**

Verify:

- home shows exactly four core creation modules;
- the default view is uncluttered;
- sidebar contains “返回工作台”“已有资产”“视频项目”“系统设置” and no core creation modules;
- Video Workshop shows exactly the eight approved topics;
- a short topic with slider value 5 continues to display/use 5 target scenes.

- [ ] **Step 4: Check browser and server errors**

Read the browser console and Streamlit server output. Expected: no new error-level messages.

- [ ] **Step 5: Final commit if verification required adjustments**

```bash
git add <adjusted-files>
git commit -m "fix: polish core workbench verification findings"
```
