# 升级路线图 2026-07

> 依据：用户 GitHub video 收藏清单（github.com/stars/MofaceJojo/lists/video）与本项目现状对照
> 目标：除 LLM 脚本生成外零额外花费 · 稳定出片 · 一键发布到各平台

## 1. 三大目标与现状差距

### 目标 A：零成本生成

| 环节 | 现状 | 结论 |
|---|---|---|
| 脚本/文案 | NousResearch API (deepseek) | 唯一付费项，用户接受 |
| TTS | OmniVoice 本地 + Edge TTS 免费 | ✅ 已达标 |
| 图像/视频生成 | ComfyUI 本地 (M4) | ✅ 已达标 |
| 泛素材 | Pexels / Pixabay 免费额度 | ✅ 已达标 |
| 排版渲染 | HyperFrames 本地 | ✅ 已达标 |

结论：零成本目标基本已达成，后续升级不得引入付费依赖（排除 muapi、Seedance 等付费 API 类项目）。

### 目标 B：稳定出片

已有：TTS 重试退避、转场不吞旁白、音频时长驱动、38 个回归测试。
缺口：任务级断点续传、ComfyUI 队列监控、成片质量自检。

### 目标 C：一键发布（差距最大）

现状 `web/pipelines/publish.py` 只有 62 行：平台按钮 = 打开各平台上传网页（douyin/kuaishou/xiaohongshu/shipinhao/bilibili/youtube 全部 `api_ready: False`）。距离"一键发送"还有完整一层集成没做。

## 2. 收藏清单对照结论

**直接采纳（免费、对口）：**

- **yikart/AiToEarn**（⭐22k，MIT，可 Docker 私有化）— 一键分发 13+ 平台（抖音/快手/B站/小红书/视频号/TikTok/YouTube/X 等），带日历排期，支持 MCP 协议。这就是目标 C 的现成答案，自建 relay 免费。
- **harry0703/MoneyPrinterTurbo**（⭐95k）— 同类标杆，值得借鉴：TTS 时间戳生成 SRT 字幕、素材去重、多宽高比批量出片、任务队列。
- **MeiGen-AI/InfiniteTalk** — 本地无限长口播数字人（图生视频），可升级 `light_avatar_video.py`。
- **facefusion/facefusion** — 本地人脸处理，数字人形象增强备选。
- **SubtitleEdit** / SRT 体系 — 平台上传需要独立字幕文件，当前字幕烧在 HTML 模板里、无 SRT 导出。
- **yt-dlp** — 内容库素材采集入口（注意版权，仅自有/授权内容）。

**借鉴思路（不引入依赖）：**

- **HKUDS/VideoAgent / calesthio/OpenMontage** — agentic 质检思路：用已有的 `image_analysis` / `video_analysis` 服务对成片做"画面-文案相关度"自动复核，对应交接优先级 2。
- **ATH-MaaS/Pixelle-Video / seme-org/open-director** — 批量模式 + 一句话全自动的产品形态参考。
- **Toonflow / huobao-drama** — 短剧方向的分镜/角色一致性设计，远期参考。

**排除（违背零成本或方向不符）：**

- SamurAIGPT/Generative-Media-Skills（muapi 付费）、dexhunter/seedance2-skill（付费 API）、NVlabs/LongLive（重模型，M4 不现实）、MoneyPrinterV2（YouTube 变现自动化，非生成主链）。

## 3. 实施顺序

### 第一阶段：发布辅助（2026-07-04 决策调整：保持手动上传）

> 用户决策：自动化发布有封号风险，各平台保持**手动上传**。发布环节只做"让手动更省事"的辅助，不做自动推送。AiToEarn 集成搁置。

1. ~~SRT 字幕导出~~ ✅ 已完成（2026-07-04）：`final.srt` 与成片同目录生成，手动上传 YouTube/B站 时直接选用。
2. **发布元数据辅助**（保留）：用已有 LLM 服务从文案生成各平台标题、话题标签、简介，展示在成片页供复制粘贴——人来点上传按钮，机器只备料。
3. ~~AiToEarn 集成~~ ⏸️ 搁置（封号风险考量）。`publish.py` 保持"打开各平台上传页"的现状即可。

### 第二阶段：稳定性加固（对应交接优先级 1/4）

4. **任务断点续传**：`frames/` 下已有分段产物，失败重跑时跳过已完成的 audio/image/segment，只补缺口。
5. **ComfyUI 队列健康检查**：生成前探测队列深度与模型加载状态，卡队列时明确报错而不是干等超时。
6. **成片自检**：拼接后自动校验总时长 = Σ音频时长、音轨无静音断层，不达标警告。

### 第三阶段：质量提升（对应交接优先级 2）

7. **相关度质检环**：用 `video_analysis` 抽帧 + LLM 评分"画面-文案相关度"，低分镜头自动重生成（上限 1 次，控制时长）。
8. **数字人升级**：InfiniteTalk 本地接入，替换/增强现有轻量数字人链路。

## 4. OpenMontage 专项对照（2026-07-03 评估：借鉴，不融合）

不融合的三个硬理由：

1. **许可证冲突**：OpenMontage 是 AGPLv3，本项目是 Apache-2.0。合入其代码会把整个项目传染成 AGPL。
2. **架构相反**：它没有 Python 编排器，靠 Claude Code/Cursor 等编码 agent 充当控制平面（"the agent is the control plane"）。本项目是确定性 Python 流水线 + Streamlit 产品界面。融合等于推倒重来。
3. **单片成本**：它每生成一部视频都要消耗一整段编码 agent 的 token（编排即推理），且演示片主要用 Veo/Kling/OpenAI 等付费 API——双重违背"除脚本外零花费"。agent 编排的随机性也与"稳定出片"矛盾。

值得借鉴并本地化复刻的技术（全部免费可实现）：

| 它的做法 | 本项目落点 |
|---|---|
| Remotion 让静态图动起来：Ken Burns 缩放/平移、视差 crossfade、粒子层（$0.15 不用视频模型出"动画"） | HyperFrames 模板加镜头运动 CSS/JS——直接改善"镜头节奏/体感"（交接优先级 2），还能减少对 ComfyUI 视频工作流的依赖 |
| WhisperX 词级字幕（TikTok 风格逐词高亮） | 本地 faster-whisper 对齐，升级路线图第一阶段的 SRT 导出为词级 |
| 多点成片自检：ffprobe 校验、抽帧检查、音频电平分析、交付承诺核对 | 路线图第二阶段"成片自检"照这个清单实现 |
| 阶段 JSON checkpoint + 断点恢复 | 路线图第二阶段"任务断点续传"的参考设计 |
| 平台渲染 profile（YouTube/TikTok 各自的宽高比/码率预设） | 配合一键发布，按目标平台自动选输出规格 |
| 参考视频反推生产计划（贴一个 YouTube 链接 → 分析节奏/结构/风格） | 远期功能，配 yt-dlp 实现 |

补充：OpenMontage 本身可以作为独立工具偶尔用（在 Claude Code 里驱动它做单件创意片），与本项目"批量稳定出片的产品"定位互补，不冲突。

## 5. 原则重申

- 不引入任何按次付费的生成 API
- 发布链路失败不能阻塞生成链路（发布是生成完成后的独立阶段）
- 每阶段结束跑全量回归测试再进下一阶段
