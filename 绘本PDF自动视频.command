#!/bin/zsh
set -e

cd "$(dirname "$0")"

PDF_PATH=$(osascript -e 'POSIX path of (choose file with prompt "选择绘本 PDF" of type {"pdf"})')
AUDIO_PATH=$(osascript -e 'POSIX path of (choose file with prompt "选择旁白音频" of type {"mp3", "wav", "m4a", "aac"})')

uv run python book_pdf_to_video.py \
  --pdf "$PDF_PATH" \
  --audio "$AUDIO_PATH"

echo ""
echo "完成。按回车关闭窗口。"
read
