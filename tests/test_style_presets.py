import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "comfykit" not in sys.modules:
    comfykit_stub = types.ModuleType("comfykit")

    class ComfyKit:  # pragma: no cover - import shim only
        pass

    comfykit_stub.ComfyKit = ComfyKit
    sys.modules["comfykit"] = comfykit_stub

from morpheus_video_studio.style_presets import (
    get_image_style_preset,
    list_image_style_presets,
    resolve_image_style_prompt,
)


def test_list_image_style_presets_returns_expected_labels():
    presets = list_image_style_presets()
    preset_ids = [preset["id"] for preset in presets]

    assert preset_ids == [
        "photo-real-portrait",
        "warm-hand-drawn-fantasy",
        "eastern-period-drama",
        "cyberpunk-neon",
        "cinematic-poster",
        "ecommerce-product",
        "healing-illustration",
        "japanese-anime",
        "childrens-picture-book",
        "historical-epic",
    ]
    assert [preset["label"] for preset in presets] == [
        "真人写真",
        "温暖手绘奇幻",
        "国风古风",
        "赛博朋克",
        "电影海报感",
        "电商产品图",
        "治愈系插画",
        "日系二次元",
        "儿童绘本",
        "历史史诗人物",
    ]


def test_get_image_style_preset_exposes_workflow_and_prompt_prefix():
    preset = get_image_style_preset("photo-real-portrait")

    assert preset["workflow"] == "selfhost/image_realisticvision_m4.json"
    assert "portrait photography" in preset["prompt_prefix"].lower()


def test_resolve_image_style_prompt_combines_prefix_and_user_prompt():
    result = resolve_image_style_prompt(
        "portrait photography, natural skin texture",
        "年轻女性，窗边自然光",
    )

    assert result.startswith("portrait photography, natural skin texture")
    assert "年轻女性" in result
