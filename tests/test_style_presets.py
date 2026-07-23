import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from morpheus_video_studio.style_presets import (
    get_image_style_preset,
    list_image_style_presets,
    resolve_image_style_prompt,
)
from web.components import style_preset_picker


def test_plain_python_import_of_style_presets_works_without_comfykit_shim():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; "
                "from morpheus_video_studio.style_presets import list_image_style_presets; "
                "print(json.dumps([preset['id'] for preset in list_image_style_presets()]))"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)[:2] == [
        "photo-real-portrait",
        "warm-hand-drawn-fantasy",
    ]


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


def test_each_image_style_preset_exposes_ui_fields():
    presets = list_image_style_presets()

    for preset in presets:
        assert preset["id"]
        assert preset["label"]
        assert preset["description"]
        assert preset["workflow"].startswith("selfhost/image_")
        assert preset["prompt_prefix"]


def test_render_image_style_preset_picker_defaults_to_first_preset(monkeypatch):
    presets = list_image_style_presets()
    first_preset = presets[0]

    class FakeStreamlit:
        def __init__(self):
            self.session_state = {}

        def radio(self, _label, _options, *, horizontal, key):
            assert horizontal is True
            return self.session_state.get(key)

    fake_streamlit = FakeStreamlit()
    monkeypatch.setattr(style_preset_picker, "st", fake_streamlit)

    selected = style_preset_picker.render_image_style_preset_picker()

    assert fake_streamlit.session_state["image_style_preset"] == first_preset["label"]
    assert selected == first_preset


def test_render_image_style_preset_picker_returns_none_when_catalog_empty(monkeypatch):
    class FakeStreamlit:
        def __init__(self):
            self.session_state = {}

        def radio(self, _label, _options, *, horizontal, key):
            raise AssertionError("radio should not render when no presets exist")

    fake_streamlit = FakeStreamlit()
    monkeypatch.setattr(style_preset_picker, "st", fake_streamlit)
    monkeypatch.setattr(style_preset_picker, "list_image_style_presets", lambda: [])

    selected = style_preset_picker.render_image_style_preset_picker()

    assert selected is None
    assert "image_style_preset" not in fake_streamlit.session_state


def test_resolve_image_style_prompt_combines_prefix_and_user_prompt():
    result = resolve_image_style_prompt(
        "portrait photography, natural skin texture",
        "年轻女性，窗边自然光",
    )

    assert result.startswith("portrait photography, natural skin texture")
    assert "年轻女性" in result
