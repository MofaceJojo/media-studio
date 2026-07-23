#!/bin/bash
# Start Morpheus Video Studio Web UI

echo "🚀 Starting Morpheus Video Studio Web UI..."
echo ""

if [ -x ".venv/bin/streamlit" ]; then
  .venv/bin/streamlit run web/app.py --server.address 127.0.0.1 --server.port 8501
else
  uv run streamlit run web/app.py --server.address 127.0.0.1 --server.port 8501
fi
