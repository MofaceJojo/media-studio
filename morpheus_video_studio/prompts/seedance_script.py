# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Seedance 2.0 video script prompt builder.

The prompt distills the public seedance2-skill guidance into a compact
project-native generator for Jimeng Seedance-ready scripts.
"""

from __future__ import annotations

import json


SEEDANCE_SCRIPT_PROMPT = """You are a professional Jimeng Seedance 2.0 video script writer.
Generate a Seedance-ready multimodal video script from the user's creative brief.

Seedance 2.0 constraints to respect:
- Output duration must be 4-15 seconds.
- Images: at most 9 files, jpeg/png/webp/bmp/tiff/gif, under 30 MB each.
- Videos: at most 3 files, mp4/mov, 2-15 seconds each, under 50 MB each.
- Audio: at most 3 files, mp3/wav, total duration at most 15 seconds.
- Total referenced files: at most 12.
- Do not recommend realistic human face uploads.
- Use @Image1, @Video1, and @Audio1 style references when assets are supplied.

Seedance prompt structure:
[subject setup] + [scene/environment] + [action/motion] + [camera movement] +
[time-segmented direction] + [transition/effects] + [audio/sound design] + [style/mood]

Camera vocabulary to use where useful:
push in, pull back, pan, tilt, follow shot, orbit shot, one-take, dolly zoom,
fisheye lens, low angle, overhead, first-person POV, whip pan, close-up,
medium shot, wide establishing shot.

Task details:
- Brief: {brief}
- Target duration: {duration_seconds} seconds
- Language: {language}
- Scenario: {scenario}
- Aspect ratio: {aspect_ratio}
- Supplied assets:
{assets_text}

Return strict JSON only with this shape:
{{
  "summary": "one sentence describing the concept",
  "duration_seconds": {duration_seconds},
  "aspect_ratio": "{aspect_ratio}",
  "asset_plan": [
    {{
      "reference": "@Image1",
      "role": "first frame / character / scene / product / other",
      "notes": "how Seedance should use it"
    }}
  ],
  "scenes": [
    {{
      "time_range": "0-3s",
      "visual": "what appears on screen",
      "camera": "camera movement and shot size",
      "motion": "subject/action movement",
      "audio": "music, sound effects, dialogue, or narration direction"
    }}
  ],
  "seedance_prompt": "complete prompt ready to paste into Seedance 2.0",
  "negative_notes": ["constraints or things to avoid"],
  "usage_notes": ["short practical notes for the operator"]
}}

Rules:
1. Match the requested output language. If language is auto, infer it from the brief.
2. Use time ranges that cover the full duration without gaps.
3. For 10 seconds or longer, include at least three time segments.
4. If assets are supplied, explicitly assign each important asset a role using @ references.
5. If no assets are supplied, write a text-only Seedance prompt and keep asset_plan empty.
6. Keep the seedance_prompt concise but complete; it should be directly usable.
7. Return valid JSON only. No Markdown fences."""


def build_seedance_script_prompt(
    brief: str,
    duration_seconds: int = 10,
    assets: list[dict[str, str]] | None = None,
    language: str = "auto",
    scenario: str = "general",
    aspect_ratio: str = "9:16",
) -> str:
    """Build an LLM prompt for a Seedance-ready video script."""
    duration_seconds = max(4, min(15, int(duration_seconds)))
    normalized_assets = assets or []
    assets_text = _format_assets(normalized_assets)
    return SEEDANCE_SCRIPT_PROMPT.format(
        brief=brief.strip(),
        duration_seconds=duration_seconds,
        language=language,
        scenario=scenario,
        aspect_ratio=aspect_ratio,
        assets_text=assets_text,
    )


def _format_assets(assets: list[dict[str, str]]) -> str:
    if not assets:
        return "- None"

    lines = []
    for index, asset in enumerate(assets[:12], start=1):
        asset_type = (asset.get("type") or "image").strip().lower()
        prefix = {
            "image": "Image",
            "video": "Video",
            "audio": "Audio",
        }.get(asset_type, "Image")
        reference = asset.get("reference") or f"@{prefix}{index}"
        label = asset.get("label") or asset.get("path") or f"asset {index}"
        role = asset.get("role") or "reference material"
        lines.append(
            f"- {reference}: type={asset_type}, label={label}, intended role={role}"
        )
    return "\n".join(lines)


def normalize_seedance_script_result(data: dict) -> dict:
    """Return a predictable Seedance script payload from a parsed LLM response."""
    return {
        "summary": str(data.get("summary", "")).strip(),
        "duration_seconds": int(data.get("duration_seconds") or 10),
        "aspect_ratio": str(data.get("aspect_ratio", "9:16")),
        "asset_plan": _list_of_dicts(data.get("asset_plan")),
        "scenes": _list_of_dicts(data.get("scenes")),
        "seedance_prompt": str(data.get("seedance_prompt", "")).strip(),
        "negative_notes": _list_of_strings(data.get("negative_notes")),
        "usage_notes": _list_of_strings(data.get("usage_notes")),
    }


def _list_of_dicts(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _list_of_strings(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
