#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8710/api}"
STORY_FILE="${TMPDIR:-/tmp}/morpheus-smoke-story.md"
PDF_FILE="${TMPDIR:-/tmp}/morpheus-smoke-picture-book.pdf"

cat >"$STORY_FILE" <<'TEXT'
雨夜里，主角在旧车站捡到一封没有署名的信。
信里提到三年前消失的列车，以及一个只有主角记得的名字。
第二天，整座城市都在假装那趟列车从未存在。
TEXT

cat >"$PDF_FILE" <<'PDF'
%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj
4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
5 0 obj << /Length 119 >> stream
BT /F1 24 Tf 72 720 Td (A picture book hero finds a glowing seed.) Tj 0 -36 Td (The bridge turns into a road home.) Tj ET
endstream endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000241 00000 n
0000000311 00000 n
trailer << /Size 6 /Root 1 0 R >>
startxref
480
%%EOF
PDF

echo "Checking API health..."
curl -fsS "$API_URL/health" | grep -q '"ok":true'

echo "Checking writing file skill..."
curl -fsS -X POST "$API_URL/writing/run" \
  -H "Content-Type: application/json" \
  --data "{\"mode\":\"video_script\",\"tone\":\"novel\",\"text\":\"\",\"source_file_paths\":\"$STORY_FILE\"}" \
  | grep -q '"source_files_used"'

echo "Checking PDF writing skill..."
curl -fsS -X POST "$API_URL/writing/run" \
  -H "Content-Type: application/json" \
  --data "{\"mode\":\"video_script\",\"tone\":\"clean\",\"text\":\"\",\"source_file_paths\":\"$PDF_FILE\"}" \
  | grep -q 'glowing seed'

echo "Generating a local MP4..."
curl -fsS -X POST "$API_URL/video/generate" \
  -H "Content-Type: application/json" \
  --data "{\"title\":\"Morpheus Smoke Test\",\"script\":\"\",\"aspect\":\"portrait\",\"seconds_per_scene\":1.5,\"voice_provider\":\"none\",\"enable_subtitles\":true,\"source_file_paths\":\"$STORY_FILE\",\"source_file_skill\":\"video_script\"}" \
  | grep -q '"ok":true'

echo "Smoke test passed."
