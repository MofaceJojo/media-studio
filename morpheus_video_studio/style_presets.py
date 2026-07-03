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

from __future__ import annotations

from typing import Final

_IMAGE_STYLE_PRESETS: Final[list[dict[str, str]]] = [
    {
        "id": "photo-real-portrait",
        "label": "真人写真",
        "description": "自然肤质、真实光影、商业写真感",
        "workflow": "selfhost/image_realisticvision_m4.json",
        "prompt_prefix": (
            "portrait photography, realistic skin texture, natural lighting, high detail, "
            "clean composition"
        ),
    },
    {
        "id": "warm-hand-drawn-fantasy",
        "label": "温暖手绘奇幻",
        "description": "柔和手绘、自然光、治愈奇幻动画感",
        "workflow": "selfhost/image_dreamshaper_m4.json",
        "prompt_prefix": (
            "warm hand-drawn fantasy animation scene, soft painterly textures, gentle daylight, "
            "whimsical environment, cinematic storytelling"
        ),
    },
    {
        "id": "eastern-period-drama",
        "label": "国风古风",
        "description": "东方审美、古典服饰、含蓄光影、戏剧氛围",
        "workflow": "selfhost/image_dreamshaper_m4.json",
        "prompt_prefix": (
            "eastern classical aesthetic, traditional Chinese period drama, elegant fabric details, "
            "refined lighting, poetic atmosphere"
        ),
    },
    {
        "id": "cyberpunk-neon",
        "label": "赛博朋克",
        "description": "霓虹城市、未来科技、强对比、潮流夜景",
        "workflow": "selfhost/image_flux.json",
        "prompt_prefix": (
            "cyberpunk neon city, futuristic technology, glowing signage, dramatic contrast, "
            "rainy night atmosphere"
        ),
    },
    {
        "id": "cinematic-poster",
        "label": "电影海报感",
        "description": "高戏剧张力、电影构图、强视觉中心、海报质感",
        "workflow": "selfhost/image_flux.json",
        "prompt_prefix": (
            "cinematic poster composition, dramatic lighting, bold focal subject, wide visual "
            "impact, premium movie-poster finish"
        ),
    },
    {
        "id": "ecommerce-product",
        "label": "电商产品图",
        "description": "干净背景、重点清晰、商品质感、营销展示",
        "workflow": "selfhost/image_realisticvision_m4.json",
        "prompt_prefix": (
            "ecommerce product photography, clean background, crisp material detail, studio lighting, "
            "commercial showcase"
        ),
    },
    {
        "id": "healing-illustration",
        "label": "治愈系插画",
        "description": "温柔色彩、松弛氛围、情绪舒缓、童话感",
        "workflow": "selfhost/image_dreamshaper_m4.json",
        "prompt_prefix": (
            "healing illustration, gentle colors, soothing atmosphere, soft textures, "
            "dreamlike comfort"
        ),
    },
    {
        "id": "japanese-anime",
        "label": "日系二次元",
        "description": "清爽日漫、角色感、明亮配色、轻快节奏",
        "workflow": "selfhost/image_dreamshaper_m4.json",
        "prompt_prefix": (
            "Japanese anime style, expressive character design, bright colors, clean linework, "
            "lively visual energy"
        ),
    },
    {
        "id": "childrens-picture-book",
        "label": "儿童绘本",
        "description": "圆润造型、亲和色彩、故事书插画、适合儿童阅读",
        "workflow": "selfhost/image_dreamshaper_m4.json",
        "prompt_prefix": (
            "children's picture book illustration, rounded forms, friendly colors, playful storytelling, "
            "soft storybook charm"
        ),
    },
    {
        "id": "historical-epic",
        "label": "历史史诗人物",
        "description": "庄重叙事、史诗气势、宏大场景、人物传记感",
        "workflow": "selfhost/image_realisticvision_m4.json",
        "prompt_prefix": (
            "historical epic portrait, grand atmosphere, solemn cinematic scale, dramatic legacy, "
            "detailed period setting"
        ),
    },
]


def list_image_style_presets() -> list[dict[str, str]]:
    return [preset.copy() for preset in _IMAGE_STYLE_PRESETS]


def get_image_style_preset(preset_id: str) -> dict[str, str]:
    for preset in _IMAGE_STYLE_PRESETS:
        if preset["id"] == preset_id:
            return preset.copy()
    raise KeyError(f"Unknown image style preset: {preset_id}")


def resolve_image_style_prompt(prefix: str, user_prompt: str) -> str:
    cleaned_prefix = (prefix or "").strip()
    cleaned_prompt = (user_prompt or "").strip()
    if cleaned_prefix and cleaned_prompt:
        return f"{cleaned_prefix}, {cleaned_prompt}"
    return cleaned_prefix or cleaned_prompt
