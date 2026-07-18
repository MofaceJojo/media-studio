from __future__ import annotations

import math
import tempfile
import textwrap
from pathlib import Path

import ffmpeg
from loguru import logger
from PIL import Image, ImageDraw, ImageFilter, ImageFont


class LightAvatarVideoService:
    """Create a lightweight 2D talking avatar video from one character image."""

    CANVAS_SIZE = (1080, 1920)
    FPS = 15

    def __init__(self) -> None:
        self._font_candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        ]

    def create_avatar_video(
        self,
        *,
        character_image: str,
        audio_path: str,
        narration_text: str,
        output_path: str,
        title: str = "",
    ) -> str:
        logger.info("Creating lightweight avatar video")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        audio_duration = self._probe_audio_duration(audio_path)
        if audio_duration <= 0:
            raise RuntimeError("Audio duration is invalid for avatar video generation.")

        total_frames = max(1, math.ceil(audio_duration * self.FPS))
        wrapped_caption = self._wrap_caption(narration_text)
        character = self._prepare_character_image(character_image)
        font_title = self._load_font(52)
        font_caption = self._load_font(56)

        with tempfile.TemporaryDirectory(prefix="light_avatar_") as temp_dir:
            frame_dir = Path(temp_dir) / "frames"
            frame_dir.mkdir(parents=True, exist_ok=True)

            for frame_index in range(total_frames):
                t = frame_index / self.FPS
                frame = self._render_frame(
                    character=character,
                    title=title,
                    caption=wrapped_caption,
                    font_title=font_title,
                    font_caption=font_caption,
                    t=t,
                )
                frame.save(frame_dir / f"{frame_index:04d}.png", format="PNG")

            self._encode_video(
                frame_pattern=str(frame_dir / "%04d.png"),
                audio_path=audio_path,
                duration=audio_duration,
                output_path=str(output),
            )

        logger.success(f"Light avatar video created: {output}")
        return str(output)

    def _probe_audio_duration(self, audio_path: str) -> float:
        probe = ffmpeg.probe(audio_path)
        return float(probe["format"]["duration"])


    def _prepare_character_image(self, image_path: str) -> Image.Image:
        image = Image.open(image_path).convert("RGBA")
        bbox = image.getbbox()
        if bbox:
            image = image.crop(bbox)
        return image

    def _render_frame(
        self,
        *,
        character: Image.Image,
        title: str,
        caption: str,
        font_title: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        font_caption: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        t: float,
    ) -> Image.Image:
        canvas = self._build_background(character)
        draw = ImageDraw.Draw(canvas, "RGBA")

        char_layer, char_box = self._place_character(character, t)
        canvas.alpha_composite(char_layer, char_box[:2])

        self._draw_title(draw, title, font_title)
        self._draw_caption(draw, caption, font_caption)
        return canvas.convert("RGB")

    def _build_background(self, character: Image.Image) -> Image.Image:
        canvas = Image.new("RGBA", self.CANVAS_SIZE, (10, 16, 28, 255))
        bg = character.copy()
        bg = bg.resize(self.CANVAS_SIZE, Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=22))
        bg = Image.blend(bg, Image.new("RGBA", self.CANVAS_SIZE, (8, 14, 26, 255)), 0.45)
        canvas.alpha_composite(bg)

        vignette = Image.new("RGBA", self.CANVAS_SIZE, (0, 0, 0, 0))
        draw = ImageDraw.Draw(vignette, "RGBA")
        draw.ellipse(
            (-120, 260, self.CANVAS_SIZE[0] + 120, self.CANVAS_SIZE[1] + 320),
            fill=(120, 160, 255, 34),
        )
        draw.rounded_rectangle(
            (70, self.CANVAS_SIZE[1] - 420, self.CANVAS_SIZE[0] - 70, self.CANVAS_SIZE[1] - 88),
            radius=42,
            fill=(12, 18, 30, 168),
        )
        vignette = vignette.filter(ImageFilter.GaussianBlur(radius=18))
        canvas.alpha_composite(vignette)
        return canvas

    def _place_character(self, character: Image.Image, t: float) -> tuple[Image.Image, tuple[int, int, int, int]]:
        max_w = int(self.CANVAS_SIZE[0] * 0.76)
        max_h = int(self.CANVAS_SIZE[1] * 0.72)
        scale = min(max_w / character.width, max_h / character.height)
        breathe = 1.0 + 0.015 * math.sin(t * 0.85)
        drift_x = int(14 * math.sin(t * 0.45))
        drift_y = int(12 * math.cos(t * 0.38))

        width = max(1, int(character.width * scale * breathe))
        height = max(1, int(character.height * scale * breathe))
        resized = character.resize((width, height), Image.Resampling.LANCZOS)

        shadow = Image.new("RGBA", (width + 40, height + 40), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow, "RGBA")
        shadow_draw.ellipse((30, height - 20, width + 10, height + 24), fill=(0, 0, 0, 110))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=18))

        layer = Image.new("RGBA", (shadow.width, shadow.height), (0, 0, 0, 0))
        layer.alpha_composite(shadow)
        layer.alpha_composite(resized, (20, 20))

        left = (self.CANVAS_SIZE[0] - layer.width) // 2 + drift_x
        top = int(self.CANVAS_SIZE[1] * 0.18) + drift_y
        return layer, (left, top, left + layer.width, top + layer.height)


    def _draw_title(
        self,
        draw: ImageDraw.ImageDraw,
        title: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> None:
        if not title.strip():
            return

        card = (80, 84, self.CANVAS_SIZE[0] - 80, 238)
        draw.rounded_rectangle(card, radius=34, fill=(8, 14, 26, 158), outline=(255, 255, 255, 30), width=2)
        title_text = self._wrap_title(title.strip(), max_width=18)
        draw.multiline_text(
            (122, 118),
            title_text,
            font=font,
            fill=(236, 242, 255, 255),
            spacing=10,
        )

    def _draw_caption(
        self,
        draw: ImageDraw.ImageDraw,
        caption: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    ) -> None:
        card = (78, self.CANVAS_SIZE[1] - 396, self.CANVAS_SIZE[0] - 78, self.CANVAS_SIZE[1] - 90)
        draw.rounded_rectangle(card, radius=38, fill=(6, 12, 22, 182), outline=(255, 255, 255, 24), width=2)
        draw.multiline_text(
            (126, self.CANVAS_SIZE[1] - 348),
            caption,
            font=font,
            fill=(247, 248, 252, 255),
            spacing=12,
            stroke_width=2,
            stroke_fill=(0, 0, 0, 220),
        )


    def _encode_video(
        self,
        *,
        frame_pattern: str,
        audio_path: str,
        duration: float,
        output_path: str,
    ) -> None:
        (
            ffmpeg
            .output(
                ffmpeg.input(frame_pattern, framerate=self.FPS),
                ffmpeg.input(audio_path).audio,
                output_path,
                t=duration,
                vcodec="libx264",
                acodec="aac",
                pix_fmt="yuv420p",
                preset="medium",
                crf=23,
                audio_bitrate="192k",
                movflags="+faststart",
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

    def _wrap_caption(self, text: str, max_lines: int = 4, max_chars_per_line: int = 16) -> str:
        cleaned = " ".join((text or "").strip().split())
        if not cleaned:
            return "请先输入一段口播文案。"

        lines: list[str] = []
        remaining = cleaned
        while remaining and len(lines) < max_lines:
            slice_end = min(len(remaining), max_chars_per_line)
            candidate = remaining[:slice_end]
            if slice_end < len(remaining) and " " in candidate:
                candidate = candidate.rsplit(" ", 1)[0] or candidate
            lines.append(candidate)
            remaining = remaining[len(candidate):].lstrip()

        if remaining:
            lines[-1] = f"{lines[-1].rstrip()}..."
        return "\n".join(lines)

    def _wrap_title(self, text: str, max_width: int) -> str:
        wrapped = textwrap.wrap(text, width=max_width) or [text]
        return "\n".join(wrapped[:2])

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        for font_path in self._font_candidates:
            if Path(font_path).exists():
                try:
                    return ImageFont.truetype(font_path, size=size)
                except Exception:
                    continue
        return ImageFont.load_default()
