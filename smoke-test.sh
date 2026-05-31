#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8710/api}"
STORY_FILE="${TMPDIR:-/tmp}/morpheus-smoke-story.md"

cat >"$STORY_FILE" <<'TEXT'
雨夜里，主角在旧车站捡到一封没有署名的信。
信里提到三年前消失的列车，以及一个只有主角记得的名字。
第二天，整座城市都在假装那趟列车从未存在。
TEXT

echo "Checking API health..."
curl -fsS "$API_URL/health" | grep -q '"ok":true'

echo "Checking writing file skill..."
curl -fsS -X POST "$API_URL/writing/run" \
  -H "Content-Type: application/json" \
  --data "{\"mode\":\"video_script\",\"tone\":\"novel\",\"text\":\"\",\"source_file_paths\":\"$STORY_FILE\"}" \
  | grep -q '"source_files_used"'

echo "Generating a local MP4..."
curl -fsS -X POST "$API_URL/video/generate" \
  -H "Content-Type: application/json" \
  --data "{\"title\":\"Morpheus Smoke Test\",\"script\":\"\",\"aspect\":\"portrait\",\"seconds_per_scene\":1.5,\"voice_provider\":\"none\",\"enable_subtitles\":true,\"source_file_paths\":\"$STORY_FILE\",\"source_file_skill\":\"video_script\"}" \
  | grep -q '"ok":true'

echo "Smoke test passed."
