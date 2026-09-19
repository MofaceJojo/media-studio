# Task 5 最终验收报告

日期：2026-08-02（Asia/Shanghai）  
工作树：`/Volumes/MACDATA/morpheus-video-studio-latest`  
分支：`codex/quick-create-and-morpheus-rebrand`  
状态：**通过（有 1 个必要修复并已提交）**

## 1. 最终状态

- 完整自动化测试、语法编译和差异检查通过。
- 原始用户题目 `《蜡笔小新》最感人的5集` 已在真实 Streamlit 页面完成交互验收。
- 最终生成参数通过现有测试替身验证；未调用付费图片或视频后端。
- 浏览器验收发现的 FAQ 嵌套折叠面板阻断已按 TDD 修复。
- 18501 服务仍在运行，最终可交付页面保留在 `http://127.0.0.1:18501/Video_Workshop`。

## 2. 服务来源与运行环境

验收开始时 18501 无监听进程。首次 `uv run` 会新建 `.venv` 并下载依赖，网络重试较多，已安全中止。随后曾用全局 Streamlit 1.45.0 启动以定位首屏错误；该版本暴露一个与锁定版本不一致的 `page_link(width=...)` 兼容问题，因此未修改产品代码，而是切换到项目锁定环境。

最终服务证据：

```text
PID: 78997
cwd: /Volumes/MACDATA/morpheus-video-studio-latest
command: /Volumes/MACDATA/morpheus-video-studio/.venv/bin/python -m streamlit run web/app.py --server.address 127.0.0.1 --server.port 18501 --server.headless true
Streamlit: 1.53.1（与 uv.lock 一致）
```

可执行依赖来自主工作树现成的 `.venv`，但进程工作目录、入口脚本、模板和运行日志路径均确认来自 `morpheus-video-studio-latest`。

## 3. 自动化命令与结果

### 修复前基线

```text
pytest -q
141 passed, 12 warnings in 10.03s

python -m compileall -q morpheus_video_studio web tests
git diff --check
exit 0，无输出
```

12 条警告均为既存 Pydantic V2 弃用提示。

### TDD 修复证据

浏览器首屏稳定复现：

```text
streamlit.errors.StreamlitAPIException:
Expanders may not be nested inside other expanders.
```

根因是 `render_faq_sidebar()` 先创建外层“常见问题” expander，又在其中为每个问题创建 expander。新增测试让测试替身遵守 Streamlit 的非嵌套规则，并验证所有问答仍被渲染。

RED：

```text
pytest -q tests/test_faq.py
1 failed
RuntimeError: nested expanders are unsupported
```

GREEN：

```text
pytest -q tests/test_faq.py
1 passed in 0.12s
```

最小修复：保留唯一外层 FAQ expander，在其中用粗体小标题加 Markdown 答案显示每个问题，不再嵌套 expander。

### 正式参数替身验收

```text
pytest -q -vv \
  tests/test_scene_draft_pipeline.py::test_output_preview_passes_scene_drafts_to_video_generation \
  tests/test_scene_draft_pipeline.py::test_generate_content_uses_scene_draft_narrations_without_llm \
  tests/test_scene_draft_pipeline.py::test_plan_visuals_uses_edited_image_prompts_before_stock_branch \
  tests/test_scene_draft_pipeline.py::test_plan_visuals_uses_edited_video_prompts_and_video_prefix

4 passed in 0.27s
```

替身将 `st.button` 设为已点击，并捕获 `morpheus_video_studio.generate_video` 参数。验证结果：

- `scene_drafts` 原样包含编辑后的 `用户旁白一/二`、`用户图片一/二`、`用户视频一/二`；
- `text == "用户旁白一\n用户旁白二"`；
- `mode == "fixed"`；
- `split_mode == "line"`；
- 内容阶段不重新调用旁白 LLM；
- 图片模板和视频模板分支均不调用图片/视频提示词生成器。

该步骤完全使用测试替身，没有点击浏览器中的真实“生成视频”按钮，也没有调用图片或视频生成后端。

### 修复后全量复验

```text
pytest -q
142 passed, 12 warnings in 9.95s

python -m compileall -q morpheus_video_studio web tests
git diff --check
exit 0，无输出
```

提交并写完报告后的最终交付检查再次执行同一组命令：`142 passed, 12 warnings in 9.99s`，后续 `compileall`、`git diff --check`、提交和 18501 工作目录核对均成功，组合命令退出码为 0。

## 4. 浏览器验收证据

浏览器：Chrome，由浏览器插件控制；只新建本次验收标签，没有关闭或修改用户其它标签。

### 原始题目与 5 张卡片

- 页面：视频工坊 → 快速创作 → 文案与生成。
- 输入：`《蜡笔小新》最感人的5集`。
- 分镜滑块保持 `5`；页面提示“本次将按 5 个目标分镜生成完整文案”。
- 首轮生成后 DOM 显示且只显示 `分镜 1` 至 `分镜 5`，对应 5 个旁白输入框与 5 个“画面提示词”折叠区域。

首轮 5 段旁白主题分别为：

1. 小新寻找失踪的父亲；
2. 小新与美冴争吵后小心翼翼地关心、和解；
3. 小新面对宠物白兔离别；
4. 危险中小新牵住家人守护他们；
5. 小新用稚嫩方式面对与爷爷的告别。

这些文本都描述了角色、关系和具体处境，不是泛化人生建议。

### 两类提示词与折叠状态

- 初次生成后的 DOM 只出现 5 个收起状态的“画面提示词”，未展开任何提示词编辑框。
- 展开分镜 1 后，分别显示独立标签和独立输入框：`图片提示词`、`视频提示词`。
- 图片提示词是静态画面构图描述；视频提示词包含人物动作、镜头跟随、气氛和动态粒子，内容与字段用途分离。

### 编辑保留

把分镜 1 图片提示词改为：

```text
验收编辑：夕阳下，小新牵着父亲的手走过春日部河堤，暖色电影光，近景。
```

提交输入触发 Streamlit 重绘后，再次读取 DOM，值仍完整保留。

### 过期提示

把主题改为 `《蜡笔小新》最搞笑的5集` 后，页面保留原草稿并显示：

```text
你已经改过主题、内容或分镜数，当前草稿可能已过期，建议重新生成。
```

### 清空

点击“清空草稿”后定向计数：

```text
旁白 textbox: 0
图片提示词 textbox: 0
视频提示词 textbox: 0
分镜 1: 0
```

证明旁白与两类提示词一起被清除。

### 最终保留页面

清空验收后重新恢复原始题目并完成第二轮生成。最终 DOM 证据：

```text
题目: 《蜡笔小新》最感人的5集
分镜数: 5
旁白输入框: 5
默认收起的画面提示词区域: 5
```

最终标签已按浏览器规范以 `deliverable` 状态保留。

### LLM 与媒体调用

- 文案/提示词使用 `google/gemma-4-26b-a4b-it:free`（OpenRouter）文本模型。
- 日志确认两轮都分别得到 5 段旁白、5 个图片提示词、5 个视频提示词。
- 服务初始化对本地 ComfyUI 仅执行 `GET /system_stats` 健康检查；没有提交媒体队列或生成任务。
- 未调用任何付费图片/视频后端。

## 5. 提交

```text
9794305 fix: complete scene draft handoff
```

提交包含：

- `web/components/faq.py`
- `tests/test_faq.py`

报告文件位于 `sdd/`，按验收材料处理，没有加入产品提交。

## 6. 自审

- 修复范围最小，只处理实际阻断所有工作台页面的 FAQ 嵌套错误。
- 回归测试验证的是可观察行为：组件在不允许嵌套 expander 的环境中仍能完整渲染问答；没有添加测试专用生产接口。
- 未触碰 Tasks 1–4 的结构化分镜数据流；现有参数替身测试继续通过。
- 未点击真实媒体生成按钮；不会产生图片或视频额度消耗。
- 最终服务与页面均来自指定 latest 工作树，页面可继续交付查看。

## 7. 疑虑与非阻断事项

1. 自由文本 LLM 会产生事实不确定或措辞瑕疵（第二轮出现“寻找寻找工作的赤屁爸爸”）。本次验收只要求具体情境而非节目集数事实核验，因此判定通过；若产品要求真实集名/集数，需接入可靠剧集资料源或检索校验。
2. 测试仍有 12 条 Pydantic 弃用警告；浏览器服务日志仍有 `use_container_width` 弃用提示和模板命名提示。这些未影响本次功能，且不属于 Tasks 1–4 失败范围。
3. 本机 latest 工作树的 `.venv` 因中止的 `uv run` 尚未完成安装；当前服务借用主工作树锁定为 1.53.1 的虚拟环境，但代码和工作目录均为 latest。后续如要求完全自包含环境，可在网络稳定时完成 `uv sync`。

## 8. 可独立复核的脱敏证据附件

证据路径：

```text
/Volumes/MACDATA/morpheus-video-studio-latest/sdd/task-5-browser-evidence.txt
```

文件大小与摘要：

```text
318 lines, 15582 bytes
SHA-256 72276b34445e2bcc7b42191dfa26759db58366ab35d38dbc7f8683d8de31c8bc
```

获取方式和证据边界已在附件首部写明，并严格分成三类：

1. **真实浏览器证据**：在标签 finalize 之前由 `tab.playwright.domSnapshot()` 与 locator `count()` 返回；附件逐字保存 5 个 `分镜 N`、5 个旁白输入、5 个默认收起的“画面提示词”标签、展开后独立的图片/视频提示词及代表性内容、编辑保留、过期警告、清空计数和最终 deliverable URL。后续没有再次操作该标签。
2. **真实服务日志**：从 PID 78997 的 Streamlit stdout 获取；保留 `Generated 5 narrations`、`Generated 5 image prompts`、`Generated 5 video prompts`、文本 LLM completion POST 以及本地 ComfyUI `GET /system_stats` 行。日志不含密钥。
3. **自动测试替身证据**：审查后从指定工作树重跑无副作用 Python 见证；模拟生成按钮已点击，打印完整 5 条 narration/image/video `scene_drafts`，并打印三个文本生成器 `await_count: 0`、`media_backend_method_calls: []`、`video_backend_method_calls: []`。此部分明确标注为自动证据，不冒充真实浏览器观察。

关键可检索摘录：

```text
finalNarrationBoxes: 5
finalCollapsedPrompts: 5
{ promptExpanderCount: 5 }
Generated 5 narrations successfully
Generated 5 image prompts
Generated 5 video prompts
captured_scene_drafts_count: 5
image_prompt_values_count: 5
video_prompt_values_count: 5
narration_generator_await_count: 0
image_prompt_generator_await_count: 0
video_prompt_generator_await_count: 0
media_backend_method_calls: []
video_backend_method_calls: []
```

真实浏览器只展开过第 1 个提示词折叠区，因此附件没有伪造其余 4 个展开态 DOM；5 个真实折叠标签由浏览器计数，5+5 个实际生成完成数由真实服务日志证明，而完整 5 行结构化值与无后端调用由可重复的自动替身证明。
