<h1 align="center">🎬 Morpheus Video Studio</h1>

<p align="center"><b>内容优先 · 零成本本地栈 · 稳定出片的 AI 音视频创作工作台</b></p>

<p align="center"><a href="README_EN.md">English</a> | <b>中文</b></p>

<p align="center">
  <a href="https://github.com/MofaceJojo/media-studio/stargazers"><img src="https://img.shields.io/github/stars/MofaceJojo/media-studio.svg" alt="Stargazers"></a>
  <a href="https://github.com/MofaceJojo/media-studio/issues"><img src="https://img.shields.io/github/issues/MofaceJojo/media-studio.svg" alt="Issues"></a>
  <a href="https://github.com/MofaceJojo/media-studio/blob/main/LICENSE"><img src="https://img.shields.io/github/license/MofaceJojo/media-studio.svg" alt="License"></a>
</p>

Morpheus Video Studio 把 **内容输入、音频生成、视频生成、数字人口播、素材复用** 串成一条完整的创作流水线。输入一段文案或一个主题，本地完成配音、配图、分镜、剪辑、字幕，产出可直接上传 YouTube / B站 / 抖音的成片。

## 🎯 三大设计目标

1. **零成本生成** —— 除了文案 LLM 的 API 调用，其余全部免费：本地 OmniVoice / Edge TTS 配音、本地 ComfyUI 出图、免费素材源（Pexels / Pixabay）、HyperFrames 本地排版渲染。
2. **稳定出片** —— 以"音频时长驱动视频时长"为核心不变量：先生成旁白、读取真实音频时长，再由它决定分镜数量与每个镜头的停留时间。转场不吞旁白，成片自动质检。
3. **手动分发，机器备料** —— 成片旁自动生成 `final.srt` 精确字幕，发布保持手动上传（规避平台风控），系统只负责把素材备好。

## ✨ 功能亮点

- ✅ **音频驱动节奏** —— 文案有多长，音频多长，视频就多长；镜头切换频率由真实旁白时长推导
- ✅ **镜头节奏预设** —— 短视频快节奏 / YouTube 舒缓节奏一键切换，横屏 16:9 自动匹配舒缓档
- ✅ **Ken Burns 镜头运动** —— 静态图自动获得缓慢缩放/平移，杜绝"一张图杵着不动"
- ✅ **成片自检门** —— 每次出片自动校验：音视频流完整性、时长偏差、静止画面、旁白断裂
- ✅ **SRT 字幕导出** —— 按每段旁白真实时长精确计时，上传平台时直接选用
- ✅ **多风格出图** —— 真人写真 / 手绘奇幻 / 国风 / 赛博朋克 / 儿童绘本等风格预设，全部基于本地模型
- ✅ **多工坊架构** —— 内容库沉淀素材，音频工坊出声音资产，视频工坊出成片，数字人口播独立成线
- ✅ **灵活画幅** —— 竖屏 9:16（抖音）/ 横屏 16:9（YouTube）/ 方形 1:1

## 📊 生成流程

```
文案（输入或 LLM 生成）
   → TTS 配音（OmniVoice / Edge TTS，读取真实时长）
   → 分镜规划（音频时长 → 镜头数量与停留时间）
   → 逐帧生产（ComfyUI 出图 → HTML 模板排版 → Ken Burns 运动 → 视频段）
   → 拼接合成（转场垫尾帧，旁白零损失）+ BGM
   → 成片自检（时长 / 静帧 / 音轨完整性）
   → final.mp4 + final.srt
```

## 🚀 快速开始

### 环境依赖

- [uv](https://docs.astral.sh/uv/getting-started/installation/)（Python 包管理器）
- [ffmpeg](https://ffmpeg.org/download.html)（`brew install ffmpeg` / `apt install ffmpeg`）
- 本地 [ComfyUI](https://github.com/Comfy-Org/ComfyUI)（图像生成，默认 `http://127.0.0.1:8188`）
- 可选：[OmniVoice Studio](https://github.com/debpalash/OmniVoice-Studio)（高质量本地 TTS，缺省时自动回退 Edge TTS）

### 启动

```bash
git clone https://github.com/MofaceJojo/media-studio.git
cd media-studio
uv run streamlit run web/app.py
```

浏览器自动打开 `http://localhost:8501`，在 **⚙️ Settings** 页配置 LLM API 与本地服务地址后即可使用。

### 页面导览

| 页面 | 用途 |
|---|---|
| 🏠 Studio | 工作台首页与快速创作入口 |
| 📚 Content Library | 沉淀 PDF、文本、书摘、金句等内容素材 |
| 🎙️ Audio Workshop | 生成可复用的旁白与声音资产 |
| 🎬 Video Workshop | 文案 + 素材 + 语音 → 成片 |
| 🤖 Digital Human | 数字人口播 |
| 🗂️ Asset Library | 生成物回收与复用 |
| ⚙️ Settings | LLM / ComfyUI / OmniVoice / 本地服务统一配置 |

## 📋 最近更新

- ✅ **2026-07**: 镜头节奏硬约束与 YouTube 舒缓档；成片自检门；SRT 字幕导出；flux-schnell (GGUF) 工作流；修复 OmniVoice 闲置卡死；`video.py` 模块化重构；GitHub Actions CI
- ✅ **2026-07**: 转场不再吞旁白（垫尾帧 + 静音填充）；TTS 瞬时故障自动重试
- ✅ **2026-06**: Morpheus 品牌重塑；快速创作流；风格标签体系；泛素材优先策略

## ❓ 常见问题

见 [docs/FAQ_CN.md](docs/FAQ_CN.md)。生成链路排查顺序：先看 `frames/*_audio.wav` 是否持续生成，再看 `frames/*_image_shot_*.png`，再看 `frames/*_segment.mp4`，最后查拼接阶段与后端服务日志。

## 🤝 致谢

本项目基于 AIDC-AI 开源的原型项目二次开发（Apache 2.0），设计另受以下开源项目启发：

- [NarratoAI](https://github.com/linyqh/NarratoAI) —— 影视解说自动化工具
- [ComfyKit](https://github.com/puke3615/ComfyKit) —— ComfyUI 工作流封装库
- [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) / [OpenMontage](https://github.com/calesthio/OpenMontage) —— 节奏与质检思路借鉴

感谢这些项目的开源精神！🙏

## 📝 许可证

本项目采用 Apache 2.0 许可证，详见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
