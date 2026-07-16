# Morpheus Video Studio 完整安装教程

> 适用:Apple Silicon Mac(M 系列芯片,建议 16GB 内存以上)。
> 全程零付费依赖,唯一可能花钱的是文案 LLM 的 API(有免费方案)。
> 安装分四层,**只装第一层就能跑通软件**,后三层按需加装。

---

## 总览:四层结构

| 层 | 装什么 | 不装会怎样 | 体积 |
|---|---|---|---|
| 1️⃣ 主程序 | 本软件(Python/Streamlit) | 无法使用 | ~2GB(含依赖) |
| 2️⃣ 文案大脑 | LLM API 密钥(免费或付费) | AI 不能写文案,只能自己输入 | 0 |
| 3️⃣ 画面引擎 | ComfyUI + 图像模型 | 不能 AI 出图/重绘,只能用泛素材和上传素材 | ~15-30GB |
| 4️⃣ 高级配音 | OmniVoice Studio | 只有 Edge TTS(也够用,音色略机械) | ~8GB |

---

## 1️⃣ 主程序(一键版)

前置:macOS 自带终端即可。逐段复制到终端执行:

```bash
# 安装 Homebrew(已有则跳过)
which brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 uv(Python 管理器)和 ffmpeg(视频处理)
brew install uv ffmpeg

# 克隆项目(想放外置盘就先 cd 到外置盘目录)
git clone https://github.com/MofaceJojo/media-studio.git
cd media-studio

# 生成配置文件
cp config.example.yaml config.yaml

# 启动(首次会自动安装全部 Python 依赖,几分钟)
uv run streamlit run web/app.py --server.address 127.0.0.1 --server.port 8501
```

浏览器打开 **http://127.0.0.1:8501** 即可看到界面。

**桌面一键启动**:仓库根目录自带 `启动 Morpheus Video Studio.command`,复制到桌面、双击即用(会自动清理端口冲突)。如果项目路径不是 `/Volumes/MACDATA/morpheus-video-studio`,编辑该文件把 `PROJECT_DIR` 改成你的路径。

---

## 2️⃣ 文案大脑(LLM)

打开软件 → **⚙️ Settings → 系统配置 → LLM 配置**,二选一:

**免费方案(能用,但高峰期限流)**
- 注册 https://openrouter.ai → Keys 页创建密钥
- 预设选 **OpenRouter**,模型填 `nvidia/nemotron-3-super-120b-a12b:free`
- 说明:免费模型每天约 50 次;账户累计充值满 $10 后涨到约 1000 次/天($10 是余额不被免费模型消耗)。撞到 429 报错就是全球免费池拥堵,等几分钟重试

**稳定方案(推荐,约 ¥10 用几个月)**
- 注册 https://platform.deepseek.com (手机号+支付宝,国内直连免代理)
- 充值 ¥10 → API Keys 创建密钥
- 预设选 **DeepSeek**,粘贴密钥保存

---

## 3️⃣ 画面引擎(ComfyUI + 模型)

### 3.1 安装 ComfyUI 本体

```bash
cd ~
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 3.2 安装必需插件(7 个)

```bash
cd ~/ComfyUI/custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
git clone https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git
git clone https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet.git
git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git
git clone https://github.com/city96/ComfyUI-GGUF.git
git clone https://github.com/Fannovel16/comfyui_controlnet_aux.git
# controlnet_aux 的依赖(Mac 上要去掉 GPU 版 onnxruntime)
grep -v "onnxruntime-gpu" comfyui_controlnet_aux/requirements.txt > /tmp/aux-req.txt
~/ComfyUI/venv/bin/pip install -r /tmp/aux-req.txt onnxruntime
```

### 3.3 下载模型

**大文件建议放外置盘再软链**(内置盘不够时):

```bash
# 示例:模型实体放外置盘,ComfyUI 里放"传送门"
mkdir -p /Volumes/你的外置盘/ComfyUI-models/models
mv ~/ComfyUI/models/* /Volumes/你的外置盘/ComfyUI-models/models/ 2>/dev/null
rm -rf ~/ComfyUI/models
ln -s /Volumes/你的外置盘/ComfyUI-models/models ~/ComfyUI/models
```

模型清单(国内用 `hf-mirror.com` 替换 `huggingface.co` 域名即可免代理直下):

| 模型文件 | 放入目录 | 来源 | 用途 |
|---|---|---|---|
| `dreamshaper_8.safetensors` (2.1GB) | `models/checkpoints/` | Civitai 搜 "DreamShaper 8" 或 HF `Lykon/DreamShaper` | 手绘/动画风出图(主力) |
| `realisticVisionV60B1_v51VAE.safetensors` (2.1GB) | `models/checkpoints/` | Civitai 搜 "Realistic Vision V6" | 写实风出图 |
| `flux1-schnell-Q3_K_S.gguf` (~5GB) | `models/unet/` | HF `city96/FLUX.1-schnell-gguf` | 高质量出图(量化版) |
| `clip_l.safetensors` + `t5xxl_fp8_e4m3fn.safetensors` | `models/clip/` | HF `comfyanonymous/flux_text_encoders` | flux 配套编码器 |
| `ae.safetensors` | `models/vae/` | HF `black-forest-labs/FLUX.1-schnell` | flux 配套 VAE |
| `v3_sd15_mm.ckpt` (1.6GB) | `models/animatediff_models/` | HF `guoyww/animatediff` | 视频动画(帧间连贯的关键) |
| `control_v11p_sd15_lineart_fp16.safetensors` (690MB) | `models/controlnet/` | HF `comfyanonymous/ControlNet-v1-1_fp16_safetensors` | AI 重绘的结构锁 |
| `control_v11p_sd15_canny_fp16.safetensors` (690MB) | `models/controlnet/` | 同上 | 结构锁备用 |
| `lcm-lora-sdv15.safetensors` (128MB) | `models/loras/` | HF `latent-consistency/lcm-lora-sdv1-5` (文件名 pytorch_lora_weights.safetensors,下载后改名) | 重绘提速 3-4 倍 |
| `ip-adapter_sd15.safetensors` (43MB) | `models/ipadapter/` | HF `h94/IP-Adapter` | 参考图引导重绘 |
| `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` (2.4GB) | `models/clip_vision/` | HF `h94/IP-Adapter`(image_encoder 目录) | 参考图编码器 |

下载命令模板(支持断点续传,断了重跑同一条命令即可):

```bash
curl -L --retry 5 -C - -o 目标路径 "https://hf-mirror.com/仓库/resolve/main/文件路径"
```

### 3.4 启动 ComfyUI

```bash
cd ~/ComfyUI && ./venv/bin/python main.py --listen 127.0.0.1 --port 8188
```

回到软件 Settings → 图像配置,ComfyUI URL 填 `http://127.0.0.1:8188`,点"测试连接"。

---

## 4️⃣ 高级配音(OmniVoice,可选)

不装的话软件自动用 Edge TTS(免费、稳定、音色一般)。想要自然音色和声音克隆再装:

```bash
cd ~
git clone https://github.com/debpalash/OmniVoice-Studio.git
cd OmniVoice-Studio
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# 启动后端(首次会自动下载 ~8GB 模型;国内先执行 export HF_ENDPOINT=https://hf-mirror.com)
./.venv/bin/uvicorn main:app --app-dir backend --host 127.0.0.1 --port 3900 --reload
```

软件里配音方式选 **OmniVoice 本地** 即可加载音色列表。

**已知问题**:连续运行数天后可能"假死"(状态显示 ready 但配音请求挂起)。处置:终止进程重启(`kill -9` 才杀得死),几秒恢复。

---

## 验证清单(装完照着过一遍)

1. Settings 页:LLM"测试连接"通过、ComfyUI"测试连接"通过
2. 音频工坊:随便输一句话 → 生成语音 → 能播放
3. 视频工坊 → 快速创作:输一个主题 → 生成 → 出 `final.mp4`(同目录有 `final.srt` 字幕)
4. 资产库 → 风格化:传一段短视频 → 滤镜档出预览

## 常见问题

| 现象 | 处置 |
|---|---|
| 启动报 "Port 8501 is not available" | 用桌面启动器(自动清理旧实例),或 `lsof -tnP -iTCP:8501 \| xargs kill` |
| 生成报 429 / rate-limited | 免费 LLM 池拥堵,等几分钟;根治靠 DeepSeek 付费方案 |
| 配音卡住不动 | OmniVoice 假死,重启它;或临时把配音方式切回"本地合成" |
| HF 模型下载中断 | 用上面的 curl 断点续传模板重跑;域名用 hf-mirror.com |
| 出图报找不到模型 | 核对模型文件名与表格完全一致(含大小写),放对子目录 |
| 本机走代理导致连不上本地服务 | 终端里 `export NO_PROXY="127.0.0.1,localhost"` 再启动 |
