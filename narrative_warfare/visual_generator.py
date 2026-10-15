#!/usr/bin/env python3
"""
Visual Scene Generator & Seed-Based Grading Engine
Creates distinct 1080x1920 (9:16) cinematic corporate-warfare scene visuals.

Features:
- Deterministic seed-based color temperature grading & palette selection
- Dynamic vignette intensity and falloff mapping
- Procedural noir corporate aesthetics (skyscraper grids, classified document layouts, market depth wireframes)
- High visual variance to prevent platform template fingerprinting
"""

import math
import random
import logging
from typing import Tuple, List, Dict, Any, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger("visual_generator")

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920


# -----------------------------------------------------------------------------
# Color Temperature & Seed-Based Palette Derivation
# -----------------------------------------------------------------------------
def derive_color_palette(seed: int) -> Dict[str, Any]:
    """
    Derives a unique, deterministic visual color grade and vignette profile from
    a 4-digit visual_style_seed. Breaks automated duplicate fingerprinting.
    """
    rng = random.Random(seed)

    # Base hue families for corporate warfare:
    # 0: Obsidian & Cyber Amber
    # 1: Midnight Navy & Ice Cyan
    # 2: Blood Crimson & Slate Grey
    # 3: Toxic Emerald & Dark Emerald
    theme_idx = rng.randint(0, 3)

    if theme_idx == 0:
        base_bg = (12, 14, 18)
        accent = (245, 158, 11)   # Amber
        highlight = (255, 214, 10)
        temp_shift = (1.05, 1.0, 0.92)  # Warm
    elif theme_idx == 1:
        base_bg = (10, 16, 26)
        accent = (14, 165, 233)   # Sky Blue
        highlight = (56, 189, 248)
        temp_shift = (0.92, 0.98, 1.08)  # Cold Steel
    elif theme_idx == 2:
        base_bg = (20, 10, 12)
        accent = (239, 68, 68)    # Crimson
        highlight = (248, 113, 113)
        temp_shift = (1.08, 0.94, 0.94)  # Blood Warmth
    else:
        base_bg = (10, 20, 16)
        accent = (16, 185, 129)   # Emerald
        highlight = (52, 211, 153)
        temp_shift = (0.95, 1.05, 0.98)  # Cyber Matrix

    # Dynamic vignette falloff (0.45 to 0.85)
    vignette_radius = rng.uniform(0.50, 0.78)
    vignette_strength = rng.uniform(0.65, 0.92)

    return {
        "seed": seed,
        "theme_idx": theme_idx,
        "base_bg": base_bg,
        "accent": accent,
        "highlight": highlight,
        "temp_shift": temp_shift,
        "vignette_radius": vignette_radius,
        "vignette_strength": vignette_strength,
    }


# -----------------------------------------------------------------------------
# Dynamic Vignette Mask Generator
# -----------------------------------------------------------------------------
def apply_dynamic_vignette(img: Image.Image, radius_factor: float = 0.65, strength: float = 0.8) -> Image.Image:
    """
    Applies a smooth radial dark vignette mask onto the image.
    """
    w, h = img.size
    # Generate radial distance map using NumPy
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    # Normalized radial distance
    dist = np.sqrt(((x - cx) / (w * radius_factor)) ** 2 + ((y - cy) / (h * radius_factor)) ** 2)
    mask = np.clip(1.0 - (dist - 0.4) * strength, 0.0, 1.0)

    arr = np.array(img, dtype=np.float32)
    for c in range(3):
        arr[:, :, c] *= mask

    return Image.fromarray(arr.astype(np.uint8))


# -----------------------------------------------------------------------------
# Procedural Noir Corporate Warfare Scenes
# -----------------------------------------------------------------------------
def get_system_font(size: int = 42, bold: bool = True) -> ImageFont.ImageFont:
    """Attempts to find a clean sans-serif system font (Arial, Segoe UI, DejaVu Sans)."""
    font_candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "seguisb.ttf" if bold else "segoeui.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "Helvetica-Bold.ttf" if bold else "Helvetica.ttf",
    ]
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def render_scene_backdrop(
    scene_type: str,
    palette: Dict[str, Any],
    topic: str,
    seed: int,
) -> np.ndarray:
    """
    Generates high-resolution 1080x1920 corporate-warfare aesthetic background frame.
    scene_type: 'HOOK', 'CHESSBOARD', 'ORDERBOOK', 'TAKEOVER'
    """
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), color=palette["base_bg"])
    draw = ImageDraw.Draw(img)

    bg_r, bg_g, bg_b = palette["base_bg"]
    acc_r, acc_g, acc_b = palette["accent"]
    hi_r, hi_g, hi_b = palette["highlight"]

    # 1. Background Grid / Radar Lines
    grid_spacing = 80
    grid_color = (min(255, bg_r + 18), min(255, bg_g + 18), min(255, bg_b + 22))
    for x in range(0, CANVAS_WIDTH, grid_spacing):
        draw.line([(x, 0), (x, CANVAS_HEIGHT)], fill=grid_color, width=1)
    for y in range(0, CANVAS_HEIGHT, grid_spacing):
        draw.line([(0, y), (CANVAS_WIDTH, y)], fill=grid_color, width=1)

    # 2. Scene-Specific Graphics
    if scene_type == "HOOK":
        # Dramatic classified dossier / biometric crosshairs
        center_x, center_y = CANVAS_WIDTH // 2, 700
        # Radar rings
        for r in [180, 320, 480]:
            draw.ellipse(
                [center_x - r, center_y - r, center_x + r, center_y + r],
                outline=(acc_r, acc_g, acc_b),
                width=2,
            )
        # Crosshair lines
        draw.line([(center_x - 520, center_y), (center_x + 520, center_y)], fill=(hi_r, hi_g, hi_b), width=2)
        draw.line([(center_x, center_y - 520), (center_x, center_y + 520)], fill=(hi_r, hi_g, hi_b), width=2)

        # Header stamp: CLASSIFIED DOSSIER
        stamp_font = get_system_font(size=36, bold=True)
        draw.rounded_rectangle([120, 160, 520, 220], radius=8, fill=(30, 0, 0, 180), outline=(239, 68, 68), width=2)
        draw.text((140, 175), "CLASSIFIED DOSSIER // EYES ONLY", font=stamp_font, fill=(239, 68, 68))

    elif scene_type == "CHESSBOARD":
        # Corporate boardroom silhouette / glass skyscraper wireframe
        for i in range(5):
            left = 120 + i * 180
            top = 450 + (i % 3) * 120
            right = left + 140
            bottom = 1400
            # Skyscraper body
            draw.rectangle([left, top, right, bottom], fill=(bg_r + 12, bg_g + 14, bg_b + 20), outline=(acc_r, acc_g, acc_b), width=2)
            # Windows
            for wy in range(top + 30, bottom - 30, 45):
                for wx in range(left + 20, right - 20, 30):
                    if (wx + wy) % 7 == 0:
                        draw.rectangle([wx, wy, wx + 15, wy + 20], fill=(hi_r, hi_g, hi_b))

    elif scene_type == "ORDERBOOK":
        # Liquidity depth / candlestick ambush lines
        rng = random.Random(seed + 101)
        candle_x = 100
        for _ in range(16):
            c_high = rng.randint(400, 800)
            c_low = c_high + rng.randint(150, 450)
            c_open = rng.randint(c_high + 30, c_low - 30)
            c_close = rng.randint(c_high + 30, c_low - 30)
            is_bull = c_close >= c_open
            c_color = (16, 185, 129) if is_bull else (239, 68, 68)

            draw.line([(candle_x + 18, c_high), (candle_x + 18, c_low)], fill=c_color, width=2)
            draw.rectangle([candle_x, min(c_open, c_close), candle_x + 36, max(c_open, c_close)], fill=c_color)
            candle_x += 56

    else:  # TAKEOVER
        # Hexagonal strategic map
        center_x, center_y = CANVAS_WIDTH // 2, 750
        for size in [200, 350, 500]:
            pts = []
            for a in range(6):
                angle = math.radians(a * 60 + 30)
                px = center_x + size * math.cos(angle)
                py = center_y + size * math.sin(angle)
                pts.append((px, py))
            draw.polygon(pts, outline=(acc_r, acc_g, acc_b), width=2)

    # 3. Topic watermark header
    header_font = get_system_font(size=30, bold=True)
    draw.text((60, 80), f"STRATEGIC CASE: {topic.upper()[:36]}", font=header_font, fill=(160, 175, 195))
    draw.line([(60, 125), (CANVAS_WIDTH - 60, 125)], fill=(acc_r, acc_g, acc_b), width=2)

    # 4. Color temperature filter shift
    arr = np.array(img, dtype=np.float32)
    tr, tg, tb = palette["temp_shift"]
    arr[:, :, 0] = np.clip(arr[:, :, 0] * tr, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] * tg, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] * tb, 0, 255)
    temp_img = Image.fromarray(arr.astype(np.uint8))

    # 5. Apply dynamic vignette
    vignetted = apply_dynamic_vignette(
        temp_img,
        radius_factor=palette["vignette_radius"],
        strength=palette["vignette_strength"],
    )

    return np.array(vignetted)


if __name__ == "__main__":
    palette = derive_color_palette(7421)
    frame = render_scene_backdrop("HOOK", palette, "Steve Jobs Boomerang Coup", 7421)
    out_im = Image.fromarray(frame)
    out_im.save("test_backdrop.png")
    print(f"Saved test backdrop: {out_im.size}")
    import os
    if os.path.exists("test_backdrop.png"):
        os.remove("test_backdrop.png")
