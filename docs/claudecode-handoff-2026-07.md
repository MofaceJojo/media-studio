# ClaudeCode Handoff - Media Studio

> 交接日期：2026-07-02
> 当前分支：`codex/quick-create-and-morpheus-rebrand`
> 说明：当前工作区不是干净状态，存在一批未提交的本地改动。接手时不要回滚这些改动，优先在现有方向上继续。

## 1. 项目定位

Media Studio 是一个以“内容优先”为核心的音视频创作平台，目标不是做通用剪辑器，而是把内容输入、音频生成、视频生成、数字人口播和素材复用串成一条工作流。

当前主线已经从单一“主题生成视频”演进为更明确的媒体工作台：

- 内容库负责沉淀 PDF、文本、书籍摘录、路线、金句等输入
- 音频工坊负责生成可复用旁白和声音资产
- 视频工坊负责把文案、素材和语音组织成成片
- 数字人口播保留为独立能力
- 资产库负责回收和复用生成物

## 2. 当前架构

### 2.1 后端

- Python / FastAPI / Streamlit 混合架构
- 核心能力集中在 `morpheus_video_studio/`
- API 入口在 `api/`
- 视频拼接、TTS、ComfyUI 调用、素材管理都在服务层完成

### 2.2 前端

- `web/` 是主 UI
- 采用 Streamlit 多页面结构
- 已拆出：
  - Studio 首页
  - Content Library
  - Audio Workshop
  - Video Workshop
  - Digital Human
  - Asset Library
  - Settings

### 2.3 关键配置

- `config.yaml` 是真实运行配置
- `config.example.yaml` 是样例
- `morpheus_video_studio/config/manager.py` 负责统一读写配置
- 设置页已统一管理 LLM、ComfyUI、HyperFrames、本地服务启动参数等

## 3. 已完成的关键方向

### 3.1 内容优先主线

- `docs/media-studio-platform-plan.md` 已明确平台方向
- `docs/audio-driven-video-preset.md` 已明确“音频时长驱动视频节奏”的推荐参数
- 视频工坊默认更偏向快速创作、文档转视频、自定义素材

### 3.2 音频与视频联动

- TTS 先生成音频，再读取真实音频时长
- 视频分镜/镜头规划会基于音频时长做基础决策
- 当前目标是让“文案有多长，音频多长，视频就多长”

### 3.3 OmniVoice 集成

- OmniVoice 作为本地高优先级 TTS 能力已接入
- 音频工坊、视频工坊、数字人口播都支持 OmniVoice 相关选择
- 已做过音色/语速的本地偏好记忆，避免每次回到默认值

### 3.4 风格与模板

- 已经有 `style presets` 体系
- 视频/图片模板和风格标签正在逐步标签化
- 当前思路是“标签选项优先”，而不是让用户手动进 ComfyUI 配 workflow

## 4. 目前最需要继续优化的地方

### 4.1 视频节奏仍需继续调

虽然主链已经按音频时长驱动，但下面这些体验仍是后续重点：

- 镜头切换还是可能偏快
- 转场和画面特效的体感还不够稳定
- 某些场景下画面和文案相关度仍不够高
- 长文案时需要更稳的 storyboard 规划

### 4.2 音频体验还可再打磨

- 转场前后存在轻微重叠感时，需要更细地处理起音/停顿
- 数字人、视频工坊、音频工坊目前对音色偏好是统一方向，但还可以进一步做成全局用户偏好

### 4.3 生成稳定性

- ComfyUI / OmniVoice / LLM 任一后端都可能成为瓶颈
- 需要持续关注超时、502、队列阻塞、模型加载卡住等问题
- 如果后续改动涉及服务启动逻辑，优先保证可恢复性，不要为了“自动化”牺牲稳定性

## 5. 目录与职责速查

- `morpheus_video_studio/services/`
  - 音视频处理、TTS、媒体生成、拼接、历史、运行时服务
- `morpheus_video_studio/pipelines/`
  - 不同业务流的后端编排
- `web/components/`
  - Streamlit 页面模块拆分
- `web/pages/`
  - 多页面入口
- `docs/`
  - 产品说明、流程说明、调试指引、交接文档
- `tests/`
  - 回归测试

## 6. 推荐启动和排查顺序

1. 先确认 `config.yaml` 可用
2. 再确认 LLM、ComfyUI、OmniVoice 服务都能连通
3. 再走音频工坊做一段短语音
4. 再走视频工坊生成短视频验证完整链路
5. 如果失败，优先看：
   - `frame_processor`
   - `tts_service`
   - `video concat`
   - 后端服务日志

## 7. 当前工作区状态提醒

当前仓库有较多未提交变更，包含但不限于：

- 新的页面结构
- 新的工具服务
- 新的交接前置功能
- 一些删除和重命名

接手时的原则：

- 不要回滚用户已有改动
- 不要把 Media Studio 重做成通用设计平台
- 先保住“内容 -> 音频 -> 视频”的主链
- 再继续做更细的节奏、相关度和稳定性优化

## 8. 给 ClaudeCode 的第一优先级任务

如果要继续推进，建议按这个顺序：

1. 优先稳定“音频时长驱动视频时长”的体验
2. 优先提升镜头节奏和相关度
3. 优先统一音色偏好记忆
4. 优先减少后端服务卡死和重试成本
5. 之后再继续扩展风格包、workflow pack 和自然语言入口

