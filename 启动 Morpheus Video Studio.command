#!/bin/bash
# Morpheus Video Studio 启动器
# 双击运行；若 8501 端口被本项目的旧实例占用，会自动清理后再启动。

PROJECT_DIR="/Volumes/MACDATA/morpheus-video-studio"
PORT=8501

cd "$PROJECT_DIR" || {
  echo "找不到项目目录：$PROJECT_DIR"
  echo "请确认外置硬盘 MACDATA 已连接。"
  read -n 1 -s -r -p "按任意键关闭..."
  exit 1
}

# 本地服务直连，不走代理
export NO_PROXY="127.0.0.1,localhost,::1,10.0.0.29"
export no_proxy="$NO_PROXY"
export PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# 端口被占用时：如果是本项目的旧 streamlit 实例，自动清掉；否则提示后退出
occupant=$(lsof -tnP -iTCP:$PORT -sTCP:LISTEN | head -1)
if [ -n "$occupant" ]; then
  occupant_cmd=$(ps -p "$occupant" -o command= 2>/dev/null)
  if echo "$occupant_cmd" | grep -q "streamlit"; then
    echo "检测到旧的 Morpheus 实例占用端口 $PORT（PID $occupant），正在关闭..."
    kill "$occupant" 2>/dev/null
    sleep 3
    if lsof -tnP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
      kill -9 "$occupant" 2>/dev/null
      sleep 2
    fi
    echo "旧实例已关闭。"
  else
    echo "端口 $PORT 被其他程序占用（PID $occupant）："
    echo "  $occupant_cmd"
    echo "请先关闭该程序，或修改本脚本中的 PORT。"
    read -n 1 -s -r -p "按任意键关闭..."
    exit 1
  fi
fi

echo "正在启动 Morpheus Video Studio..."
echo "启动成功后请打开：http://127.0.0.1:$PORT"
echo ""

if [ -x ".venv/bin/streamlit" ]; then
  .venv/bin/streamlit run web/app.py --server.address 127.0.0.1 --server.port $PORT
else
  uv run streamlit run web/app.py --server.address 127.0.0.1 --server.port $PORT
fi
