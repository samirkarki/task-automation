"""
Intro / Outro Bumper Renderer.
Generates a 10-second animated 1920x1080 MP4 card for long-form compilations.
Uses Pillow to build a static frame then FFmpeg to animate it (Ken Burns zoom).
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("clipping.transformation.bumper_renderer")

try:
    from common.whisper_utils import ensure_ffmpeg_on_path
    ensure_ffmpeg_on_path()
except Exception:
    pass


def _load_font(size: int, bold: bool = False):
    """Load TrueType font with graceful cross-platform fallback."""
    from PIL import ImageFont  # noqa
    suffix = "-Bold" if bold else ""
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suffix}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{suffix}.ttf",
        f"C:/Windows/Fonts/arial{'bd' if bold else ''}.ttf",
        f"C:/Windows/Fonts/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_bumper(
    channel_brand_name: str,
    game_title: str,
    output_path: Path,
    avatar_path: Optional[str] = None,
    duration: float = 10.0,
    accent_color: str = "0x00FFE5",
    episode_label: str = "",
) -> Optional[Path]:
    """
    Renders a 10-second 1920x1080 MP4 bumper card.

    Visual layout:
        Dark gradient background
        [Channel name — large centered]
        [Game title — subtitle]
        [Episode label — small]
        [Avatar circle — top-right if available]

    Animation: Slow Ken Burns zoom (scale 1.0 → 1.03 over 10 seconds).
    Falls back to static image if Ken Burns fails.
    """
    try:
        from PIL import Image, ImageDraw  # noqa
    except ImportError:
        logger.warning("Pillow not installed — bumper rendering disabled.")
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Build static 1920x1080 frame ---
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), (5, 5, 15))
    draw = ImageDraw.Draw(img)

    # Dark gradient (top → bottom)
    for y in range(H):
        t = y / H
        r = int(5 + t * 10)
        g = int(5 + t * 15)
        b = int(15 + t * 30)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Accent lines (top and bottom, 8px)
    # accent_color is "0xRRGGBB" — convert to tuple
    try:
        hex_str = accent_color.replace("0x", "").replace("#", "")
        accent_rgb = tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        accent_rgb = (0, 255, 229)
    draw.rectangle([0, 0, W, 8], fill=accent_rgb)
    draw.rectangle([0, H - 8, W, H], fill=accent_rgb)

    # Avatar (optional, top-right corner)
    if avatar_path and Path(avatar_path).exists():
        try:
            from PIL import Image as _Image  # noqa
            av = _Image.open(avatar_path).convert("RGBA").resize((160, 160))
            mask = _Image.new("L", (160, 160), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 159, 159], fill=255)
            av_circle = _Image.new("RGBA", (160, 160), (0, 0, 0, 0))
            av_circle.paste(av, mask=mask)
            img_rgba = img.convert("RGBA")
            img_rgba.paste(av_circle, (W - 200, 60), av_circle)
            img = img_rgba.convert("RGB")
            draw = ImageDraw.Draw(img)
        except Exception as e:
            logger.debug(f"Avatar paste skipped: {e}")

    # Fonts
    font_channel = _load_font(90, bold=True)
    font_game = _load_font(52)
    font_episode = _load_font(34)

    def draw_centered(text: str, font, y_center: int, color=(255, 255, 255)):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y_center), text, fill=color, font=font)

    draw_centered(channel_brand_name, font_channel, H // 2 - 110)
    draw_centered(game_title, font_game, H // 2 + 20, color=(180, 220, 255))
    if episode_label:
        draw_centered(episode_label, font_episode, H // 2 + 90, color=(140, 140, 160))

    # Save static frame as PNG
    static_frame_path = output_path.with_suffix(".frame.png")
    img.save(str(static_frame_path))

    # --- Animate with FFmpeg: Ken Burns zoom + fade in/out ---
    frames = int(duration * 25)
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(static_frame_path),
        "-vf", (
            f"scale=8000:-1,"
            f"zoompan=z='min(zoom+0.0004,1.03)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={frames}:fps=25:s=1920x1080,"
            f"fade=t=in:st=0:d=0.5,"
            f"fade=t=out:st={duration - 0.8:.2f}:d=0.8"
        ),
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-an",
        "-movflags", "+faststart",
        str(output_path),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.warning(f"Ken Burns bumper failed — falling back to static: {res.stderr[:200]}")
        fallback_cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(static_frame_path),
            "-vf", f"fade=t=in:st=0:d=0.5,fade=t=out:st={duration - 0.8:.2f}:d=0.8",
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-an",
            str(output_path),
        ]
        fb_res = subprocess.run(fallback_cmd, capture_output=True, text=True)
        if fb_res.returncode != 0:
            logger.error(f"Bumper fallback render also failed: {fb_res.stderr[:200]}")
            # Clean up static frame
            static_frame_path.unlink(missing_ok=True)
            return None

    static_frame_path.unlink(missing_ok=True)
    logger.info(f"Bumper rendered: {output_path}")
    return output_path
