#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  for job in $(jobs -p); do
    kill "$job" 2>/dev/null || true
  done
}
trap cleanup EXIT

if [[ ! -f "$ROOT_DIR/backend/.venv/bin/activate" ]]; then
  echo "Backend virtual environment is missing. Run ./install.sh first."
  exit 1
fi

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "Frontend dependencies are missing. Run ./install.sh first."
  exit 1
fi

cd "$ROOT_DIR/backend"
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8710 &

cd "$ROOT_DIR/frontend"
npm run dev -- --port 5173 &

echo "Morpheus Video Studio"
echo "WebUI:   http://localhost:5173"
echo "Backend: http://127.0.0.1:8710"
wait
