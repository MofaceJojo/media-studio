#!/bin/zsh
set -e

cd "$(dirname "$0")"

PDF_PATH=$(osascript -e 'POSIX path of (choose file with prompt "选择绘本 PDF" of type {"pdf"})')
USE_AUDIO=$(osascript -e 'button returned of (display dialog "是否选择旁白音频？\n不选择时会根据 PDF 内容自动生成旁白。" buttons {"自动生成旁白", "选择音频"} default button "自动生成旁白")')

if [[ "$USE_AUDIO" == "选择音频" ]]; then
  AUDIO_PATH=$(osascript -e 'POSIX path of (choose file with prompt "选择旁白音频" of type {"mp3", "wav", "m4a", "aac"})')
  uv run python book_pdf_to_video.py \
    --pdf "$PDF_PATH" \
    --audio "$AUDIO_PATH"
else
  uv run python book_pdf_to_video.py \
    --pdf "$PDF_PATH"
fi

echo ""
echo "完成。按回车关闭窗口。"
read
