from pathlib import Path

from morpheus_video_studio.utils.subtitle_export import export_srt, _format_timestamp


def test_format_timestamp_rounds_milliseconds() -> None:
    assert _format_timestamp(0) == "00:00:00,000"
    assert _format_timestamp(2.934) == "00:00:02,934"
    assert _format_timestamp(3661.5) == "01:01:01,500"


def test_export_srt_lays_segments_back_to_back(tmp_path: Path) -> None:
    srt_path = tmp_path / "final.srt"
    export_srt(
        [
            ("第一句旁白。", 2.93),
            ("第二句旁白，稍微长一点。", 5.64),
            ("第三句收尾。", 4.07),
        ],
        str(srt_path),
    )

    content = srt_path.read_text(encoding="utf-8")
    blocks = [block for block in content.split("\n\n") if block.strip()]
    assert len(blocks) == 3
    assert "00:00:00,000 --> 00:00:02,930" in blocks[0]
    assert "00:00:02,930 --> 00:00:08,570" in blocks[1]
    assert "第三句收尾。" in blocks[2]


def test_export_srt_skips_empty_segments_but_keeps_timeline(tmp_path: Path) -> None:
    srt_path = tmp_path / "final.srt"
    export_srt(
        [
            ("开场白。", 3.0),
            ("", 2.0),  # silent gap keeps its slot on the timeline
            ("结束语。", 3.0),
        ],
        str(srt_path),
    )

    content = srt_path.read_text(encoding="utf-8")
    assert "00:00:05,000 --> 00:00:08,000" in content
    assert content.count("-->") == 2
