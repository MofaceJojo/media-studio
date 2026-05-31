#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v /opt/homebrew/bin/python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="/opt/homebrew/bin/python3.12"
  elif command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="python3.12"
  else
    PYTHON_BIN="python3"
  fi
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required. Install it first, for example: brew install ffmpeg"
  exit 1
fi

cd "$ROOT_DIR/backend"
"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

cd "$ROOT_DIR/frontend"
npm install

echo "Morpheus Video Studio installed."
echo "Run ./run.sh and open http://localhost:5173"
