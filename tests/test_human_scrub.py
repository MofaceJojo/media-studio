from morpheus_video_studio.utils.content_generators import scrub_human_terms


def test_removes_english_person():
    out = scrub_human_terms("An elderly doctor taking a patient's pulse at a wooden table")
    for bad in ("elderly", "doctor", "patient"):
        assert bad not in out.lower(), f"'{bad}' leaked: {out}"
    assert "wooden table" in out  # 场景保留


def test_removes_chinese_person():
    out = scrub_human_terms("老中医为患者把脉，桌上摆着当归")
    assert "老中医" not in out and "患者" not in out
    assert "当归" in out


def test_hands_and_face_removed():
    out = scrub_human_terms("close-up of hands holding herbs, gentle face")
    assert "hands" not in out.lower() and "face" not in out.lower()
    assert "herbs" in out


def test_pure_object_prompt_untouched():
    s = "macro shot of dried danggui roots on a stone slab, soft daylight"
    assert scrub_human_terms(s) == s
