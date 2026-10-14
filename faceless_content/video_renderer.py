#!/usr/bin/env python3
"""
Faceless Video Renderer (9:16 Short-Form MP4 Generator)
Uses MoviePy and Pillow to render high-retention 1080x1920 vertical videos
with animated chart backgrounds, centered bold subtitles, and synchronized voiceover.
Does not require ImageMagick by rendering text overlays directly with Pillow.
"""

import os
import sys
import math
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("video_renderer")

# Video Constants
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
DEFAULT_FPS = 24


# -----------------------------------------------------------------------------
# Visual Frame Generators (PIL-based, 100% Portable)
# -----------------------------------------------------------------------------
def get_font(size: int = 48, bold: bool = True) -> ImageFont.ImageFont:
    """
    Attempts to load a clean sans-serif system font or falls back to default.
    """
    font_candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "LiberationSans-Bold.ttf" if bold else "LiberationSans.ttf",
        "Roboto-Bold.ttf" if bold else "Roboto.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
    ]

    for cand in font_candidates:
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue

    return ImageFont.load_default()


def create_dynamic_background_frame(t: float, total_duration: float) -> np.ndarray:
    """
    Generates a dynamic 1080x1920 dark financial background with animated grid lines,
    gradient lighting, and simulated candlestick chart bars.
    """
    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT), color=(12, 16, 28))
    draw = ImageDraw.Draw(img)

    # 1. Subtle radial/vertical glow (greenish-cyan bull tint)
    pulse = 0.5 + 0.5 * math.sin(t * 1.5)
    glow_color = (int(16 + 20 * pulse), int(32 + 35 * pulse), int(50 + 25 * pulse))
    draw.rectangle([0, 0, VIDEO_WIDTH, 700], fill=glow_color)

    # 2. Subtle grid lines
    grid_spacing = 90
    offset_y = int((t * 25) % grid_spacing)
    for y in range(offset_y, VIDEO_HEIGHT, grid_spacing):
        draw.line([(0, y), (VIDEO_WIDTH, y)], fill=(24, 34, 52), width=1)
    for x in range(0, VIDEO_WIDTH, grid_spacing):
        draw.line([(x, 0), (x, VIDEO_HEIGHT)], fill=(24, 34, 52), width=1)

    # 3. Dynamic Stock Chart Graphic in center (animated moving candles)
    chart_y_center = 800
    candle_count = 18
    candle_width = 28
    spacing = 55
    start_x = 70

    for i in range(candle_count):
        cx = start_x + (i * spacing)
        # Pseudo-random dynamic candle heights based on index and time
        phase = (t * 0.8) + (i * 0.4)
        c_open = chart_y_center + int(math.sin(phase) * 140)
        c_close = c_open - int(math.cos(phase + 0.3) * 90)

        is_bullish = c_close <= c_open
        color = (16, 215, 138) if is_bullish else (244, 63, 94)  # Neon Emerald vs Ruby

        top_val = min(c_open, c_close)
        bot_val = max(c_open, c_close)
        wick_high = top_val - 25
        wick_low = bot_val + 25

        # Draw wick
        draw.line([(cx + candle_width // 2, wick_high), (cx + candle_width // 2, wick_low)], fill=color, width=3)
        # Draw candle body
        draw.rectangle([cx, top_val, cx + candle_width, bot_val], fill=color)

    # 4. Top Header Card
    header_box = [60, 140, VIDEO_WIDTH - 60, 300]
    draw.rounded_rectangle(header_box, radius=20, fill=(20, 26, 42), outline=(45, 212, 191), width=2)

    font_title = get_font(size=44, bold=True)
    font_sub = get_font(size=28, bold=False)
    draw.text((VIDEO_WIDTH // 2, 190), "NEPSE MARKET INTELLIGENCE", font=font_title, fill=(255, 255, 255), anchor="mm")
    draw.text((VIDEO_WIDTH // 2, 250), "DAILY DATA-DRIVEN ANALYSIS", font=font_sub, fill=(45, 212, 191), anchor="mm")

    # 5. Bottom Call to Action Card
    footer_box = [60, VIDEO_HEIGHT - 320, VIDEO_WIDTH - 60, VIDEO_HEIGHT - 180]
    draw.rounded_rectangle(footer_box, radius=20, fill=(18, 22, 36), outline=(234, 179, 8), width=2)

    font_cta = get_font(size=36, bold=True)
    font_disclaimer = get_font(size=22, bold=False)
    draw.text((VIDEO_WIDTH // 2, VIDEO_HEIGHT - 265), "SUBSCRIBE FOR DAILY SIGNALS", font=font_cta, fill=(234, 179, 8), anchor="mm")
    draw.text((VIDEO_WIDTH // 2, VIDEO_HEIGHT - 215), "Automated research only. Not financial advice.", font=font_disclaimer, fill=(148, 163, 184), anchor="mm")

    return np.array(img)


def create_subtitle_overlay_image(text: str) -> np.ndarray:
    """
    Renders a centered bold, high-contrast subtitle card with drop shadow.
    """
    # Transparent canvas
    img = Image.new("RGBA", (VIDEO_WIDTH, 320), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center_x = VIDEO_WIDTH // 2
    center_y = 160

    # Draw rounded background pill behind text
    font = get_font(size=56, bold=True)
    bbox = draw.textbbox((center_x, center_y), text, font=font, anchor="mm")
    padding_x = 40
    padding_y = 20
    pill_box = [bbox[0] - padding_x, bbox[1] - padding_y, bbox[2] + padding_x, bbox[3] + padding_y]

    # Dark translucent pill
    draw.rounded_rectangle(pill_box, radius=16, fill=(10, 15, 26, 210), outline=(250, 204, 21, 230), width=3)

    # Black text shadow
    shadow_offset = 3
    draw.text((center_x + shadow_offset, center_y + shadow_offset), text, font=font, fill=(0, 0, 0, 255), anchor="mm")
    # Vibrant Yellow / Gold Text
    draw.text((center_x, center_y), text, font=font, fill=(255, 235, 59, 255), anchor="mm")

    return np.array(img)


# -----------------------------------------------------------------------------
# MoviePy Video Composer
# -----------------------------------------------------------------------------
def render_short_video(
    audio_path: Path,
    subtitles: List[Dict[str, Any]],
    output_video_path: Path,
    fps: int = DEFAULT_FPS,
) -> Path:
    """
    Renders the complete 9:16 vertical video synchronized to the provided audio file.
    """
    from moviepy.editor import (
        AudioFileClip,
        VideoClip,
        ImageClip,
        CompositeVideoClip,
    )

    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Loading audio from {audio_path}...")
    audio_clip = AudioFileClip(str(audio_path))
    duration = audio_clip.duration

    logger.info(f"Audio duration: {duration:.2f}s. Preparing video frames at {fps} FPS...")

    # 1. Dynamic background clip
    def make_frame(t):
        return create_dynamic_background_frame(t, duration)

    bg_clip = VideoClip(make_frame, duration=duration).set_fps(fps)

    # 2. Build subtitle overlay clips
    subtitle_clips = []
    sub_y_pos = 1100  # Positioned comfortably in optical center above bottom banners

    for item in subtitles:
        text = item["text"]
        start_t = item["start"]
        end_t = min(item["end"], duration)
        clip_dur = max(0.2, end_t - start_t)

        sub_img_np = create_subtitle_overlay_image(text)
        sub_clip = (
            ImageClip(sub_img_np, ismask=False)
            .set_start(start_t)
            .set_duration(clip_dur)
            .set_position(("center", sub_y_pos))
        )
        subtitle_clips.append(sub_clip)

    # 3. Composite Video & Attach Audio
    logger.info(f"Compositing {len(subtitle_clips)} subtitle clips over animated background...")
    video = CompositeVideoClip([bg_clip, *subtitle_clips], size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    video = video.set_audio(audio_clip).set_duration(duration)

    # 4. Write final MP4 file
    logger.info(f"Encoding final MP4 to {output_video_path} (codec=libx264, audio=aac)...")
    video.write_videofile(
        str(output_video_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",  # Super fast rendering for L4 server throughput
        threads=4,
        logger=None,  # Suppress moviepy verbose progress bar in server logs
    )

    # Close clips to release file locks and memory
    audio_clip.close()
    video.close()

    logger.info(
        f"Video render complete: {output_video_path} ({output_video_path.stat().st_size / (1024 * 1024):.2f} MB)"
    )
    return output_video_path
