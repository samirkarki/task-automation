"""
Attribution Badge Generator.
Creates a semi-transparent PNG badge showing channel branding.
Used in:
  - Shorts: corner overlay when no facecam detected
  - Long-form: bumper cards and segment title overlays
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("clipping.transformation.attribution_badge")

_PILLOW_AVAILABLE = False
try:
    from PIL import Image, ImageDraw, ImageFont
    _PILLOW_AVAILABLE = True
except ImportError:
    logger.warning(
        "Pillow not installed — attribution badge generation disabled. "
        "Run: pip install Pillow"
    )


def generate_attribution_badge(
    channel_name: str,
    avatar_path: Optional[str] = None,
    output_path: str = "badge.png",
    width: int = 420,
    height: int = 110,
    subtitle: str = "Original Streamer",
) -> Optional[str]:
    """
    Generates a semi-transparent attribution badge PNG.

    Layout:
        [Avatar/Initial circle 80x80]  [Channel Name (bold)]
                                       [subtitle]

    Args:
        channel_name: Displayed channel name.
        avatar_path: Optional path to avatar PNG/JPEG.
                     If None, generates an initial-based circle.
        output_path: Where to write the output PNG.
        width: Badge width in pixels (default 420).
        height: Badge height in pixels (default 110).
        subtitle: Small label under channel name (default "Original Streamer").

    Returns:
        output_path string if successful, None on failure.
    """
    if not _PILLOW_AVAILABLE:
        return None

    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F811

        # --- Canvas ---
        badge = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(badge)

        # Semi-transparent dark background (rounded rect)
        bg_color = (10, 10, 20, 180)        # near-black, 70% opacity
        border_color = (0, 255, 229, 220)   # cyan #00FFE5
        margin = 4
        draw.rounded_rectangle(
            [margin, margin, width - margin, height - margin],
            radius=18,
            fill=bg_color,
            outline=border_color,
            width=2,
        )

        # --- Avatar circle (80x80, centered vertically, left margin 15) ---
        avatar_x, avatar_y = 15, (height - 80) // 2
        avatar_size = 80

        avatar_img = None
        if avatar_path and Path(avatar_path).exists():
            try:
                raw = Image.open(avatar_path).convert("RGBA")
                raw = raw.resize((avatar_size, avatar_size), Image.LANCZOS)
                # Circular mask
                mask = Image.new("L", (avatar_size, avatar_size), 0)
                ImageDraw.Draw(mask).ellipse(
                    [0, 0, avatar_size - 1, avatar_size - 1], fill=255
                )
                avatar_img = Image.new("RGBA", (avatar_size, avatar_size), (0, 0, 0, 0))
                avatar_img.paste(raw, mask=mask)
            except Exception:
                avatar_img = None

        if avatar_img is None:
            # Generate initial-based colored circle
            initial = (channel_name.strip()[0].upper()) if channel_name.strip() else "?"
            avatar_img = Image.new("RGBA", (avatar_size, avatar_size), (0, 0, 0, 0))
            adraw = ImageDraw.Draw(avatar_img)
            adraw.ellipse(
                [0, 0, avatar_size - 1, avatar_size - 1],
                fill=(0, 200, 180, 255),
            )
            font_initial = _load_font(36, bold=True)
            bbox = adraw.textbbox((0, 0), initial, font=font_initial)
            tx = (avatar_size - (bbox[2] - bbox[0])) // 2
            ty = (avatar_size - (bbox[3] - bbox[1])) // 2
            adraw.text((tx, ty), initial, fill=(255, 255, 255, 255), font=font_initial)

        badge.paste(avatar_img, (avatar_x, avatar_y), avatar_img)

        # --- Text block ---
        text_x = avatar_x + avatar_size + 14
        font_name = _load_font(26, bold=True)
        font_sub = _load_font(18, bold=False)

        # Truncate channel name if too long
        display_name = channel_name if len(channel_name) <= 20 else channel_name[:18] + "\u2026"

        name_y = (height // 2) - 20
        draw.text((text_x, name_y), display_name, fill=(255, 255, 255, 255), font=font_name)
        draw.text((text_x, name_y + 32), subtitle, fill=(180, 180, 180, 220), font=font_sub)

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        badge.save(str(out), "PNG")
        logger.info(f"Attribution badge generated: {out} ({width}x{height}px)")
        return str(out)

    except Exception as e:
        logger.warning(f"Failed to generate attribution badge: {e}")
        return None


def _load_font(size: int, bold: bool = False) -> "ImageFont.FreeTypeFont":
    """Load a TrueType font with graceful fallback."""
    from PIL import ImageFont  # noqa: F811

    suffix = "-Bold" if bold else ""
    candidates = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suffix}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{suffix}.ttf",
        f"C:/Windows/Fonts/arial{'bd' if bold else ''}.ttf",
        f"C:/Windows/Fonts/Arial{'Bold' if bold else ''}.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def fetch_channel_avatar(channel_url: str, output_dir: str) -> Optional[str]:
    """
    Best-effort: download channel avatar via yt-dlp --write-thumbnail.
    Returns path to downloaded thumbnail or None on failure.
    """
    try:
        import subprocess
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                "yt-dlp", "--write-thumbnail", "--skip-download",
                "--playlist-items", "1",
                "--output", str(out_dir / "avatar.%(ext)s"),
                channel_url,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        for ext in ["jpg", "jpeg", "png", "webp"]:
            candidate = out_dir / f"avatar.{ext}"
            if candidate.exists():
                logger.info(f"Channel avatar downloaded: {candidate}")
                return str(candidate)
        logger.debug(f"yt-dlp avatar fetch produced no file. stderr: {result.stderr[:200]}")
    except Exception as e:
        logger.debug(f"Avatar fetch skipped: {e}")
    return None
