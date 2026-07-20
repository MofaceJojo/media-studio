import subprocess
from pathlib import Path

import ffmpeg

from morpheus_video_studio.services.video import VideoService


def _make_speech_video(path: Path) -> None:
    """4s: narration(4000Hz) on 0-1s & 3-4s, silent 1-3s. High freq so a steep
    lowpass can isolate the low-freq BGM for measurement."""
    v = ffmpeg.input("color=c=gray:s=160x120:r=10:d=4", f="lavfi").video
    a = ffmpeg.input(
        "aevalsrc=0.5*sin(4000*2*PI*t)*lt(mod(t\\,3)\\,1):s=44100:d=4", f="lavfi"
    ).audio
    ffmpeg.output(v, a, str(path), vcodec="libx264", acodec="aac", pix_fmt="yuv420p") \
        .overwrite_output().run(capture_stdout=True, capture_stderr=True)


def _make_bgm(path: Path) -> None:
    a = ffmpeg.input("sine=frequency=100:sample_rate=44100:duration=4", f="lavfi").audio
    ffmpeg.output(a, str(path), acodec="aac").overwrite_output() \
        .run(capture_stdout=True, capture_stderr=True)


def _bgm_level(video: str, t0: float, t1: float) -> float:
    """Mean dB of the low BGM band; steep lowpass chain kills the 4000Hz narration."""
    r = subprocess.run(
        ["ffmpeg", "-ss", str(t0), "-to", str(t1), "-i", video,
         "-af", "lowpass=f=200,lowpass=f=200,lowpass=f=200,volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    for line in r.stderr.splitlines():
        if "mean_volume" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0])
    return 0.0


def test_bgm_ducks_under_narration(tmp_path):
    video, bgm, out = tmp_path / "v.mp4", tmp_path / "bgm.m4a", tmp_path / "ducked.mp4"
    _make_speech_video(video)
    _make_bgm(bgm)
    VideoService().add_bgm(str(video), str(bgm), str(out), bgm_volume=0.5, duck=True)

    speaking = _bgm_level(str(out), 0.2, 0.8)
    silent = _bgm_level(str(out), 1.5, 2.5)
    assert silent - speaking > 6.0, f"no ducking: speaking={speaking}dB silent={silent}dB"


def test_bgm_flat_mix_when_duck_off(tmp_path):
    video, bgm, out = tmp_path / "v.mp4", tmp_path / "bgm.m4a", tmp_path / "flat.mp4"
    _make_speech_video(video)
    _make_bgm(bgm)
    VideoService().add_bgm(str(video), str(bgm), str(out), bgm_volume=0.5, duck=False)
    # No ducking: BGM roughly equal in both segments
    assert abs(_bgm_level(str(out), 0.2, 0.8) - _bgm_level(str(out), 1.5, 2.5)) < 4.0
