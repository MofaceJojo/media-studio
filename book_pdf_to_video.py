#!/usr/bin/env python3
"""Run the picture-book PDF automation pipeline from the command line."""

import argparse
import asyncio
from pathlib import Path

from pixelle_video.pipelines.book_pdf import BookPDFVideoPipeline
from pixelle_video.service import PixelleVideoCore


def parse_args():
    parser = argparse.ArgumentParser(description="PDF + audio -> regenerated captioned video")
    parser.add_argument("--pdf", required=True, help="Input PDF path")
    parser.add_argument("--audio", required=True, help="Narration audio path")
    parser.add_argument("--output", help="Output mp4 path")
    parser.add_argument("--title", default="Picture Book Video")
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--no-redraw", action="store_true", help="Skip ComfyUI redraw and use page images directly")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--steps", type=int, default=18)
    parser.add_argument("--denoise", type=float, default=0.68)
    parser.add_argument("--cfg", type=float, default=7.0)
    parser.add_argument("--speed", type=float, default=1.12)
    return parser.parse_args()


async def main():
    args = parse_args()
    output = args.output
    if not output:
        out_dir = Path("/Volumes/MACDATA/成片/Pixelle自动绘本视频")
        out_dir.mkdir(parents=True, exist_ok=True)
        output = str(out_dir / f"{Path(args.pdf).stem.replace(' ', '_')}_自动重绘字幕版.mp4")

    core = PixelleVideoCore()
    await core.initialize()
    pipeline = BookPDFVideoPipeline(core)

    def progress(message: str, value: float):
        print(f"{value:>5.0%} {message}", flush=True)

    try:
        result = await pipeline(
            pdf_path=args.pdf,
            audio_path=args.audio,
            output_path=output,
            title=args.title,
            width=args.width,
            height=args.height,
            steps=args.steps,
            denoise=args.denoise,
            cfg=args.cfg,
            speed=args.speed,
            max_pages=args.max_pages,
            redraw_pages=not args.no_redraw,
            progress_callback=progress,
        )
        print(result.output_path)
    finally:
        await core.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
