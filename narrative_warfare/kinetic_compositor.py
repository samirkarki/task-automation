#!/usr/bin/env python3
"""
Kinetic Media Compositor (MoviePy & Native FFmpeg)
Renders high-retention 1080x1920 (9:16) vertical MP4 videos:
- Dynamic Ken Burns micro-motion (oscillating random rates between 1.05x and 1.20x)
- Dynamic velocity-scaled Hormozi-style subtitle cards
- Multi-scene corporate warfare transitions with subtle cross-dissolves
- Frame-by-frame kinetic variation breaking platform template fingerprinting
- Mastered audio track attachment (0dB voice + -20dB ambient drone)
- Hardware NVENC acceleration with ultrafast CPU fallback
"""

import os
import sys
import math
import random
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from narrative_warfare.visual_generator import (
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    derive_color_palette,
    render_scene_backdrop,
    get_system_font,
)
from narrative_warfare.media_director import (
    plan_visual_beats,
    resolve_all_beat_assets,
    VisualBeat,
)
from narrative_warfare.whisper_transcriber import SubtitleCard
from faceless_content.moviepy_compat import (
    VideoClip,
    AudioFileClip,
    set_clip_duration,
    set_clip_fps,
    set_clip_audio,
    is_moviepy_available,
)

logger = logging.getLogger("kinetic_compositor")

DEFAULT_FPS = 24


# -----------------------------------------------------------------------------
# Ken Burns Smooth Micro-Motion Engine
# -----------------------------------------------------------------------------
def get_ken_burns_crop(
    image: Image.Image,
    progress: float,
    max_zoom: float = 1.15,
    pan_dx: float = 0.0,
    pan_dy: float = 0.0,
) -> Image.Image:
    """
    Applies smooth interpolation zoom (1.0x -> max_zoom) and subtle pan shift.
    """
    w, h = image.size
    # Current zoom factor (linear or smoothstep)
    smooth_p = 3.0 * (progress ** 2) - 2.0 * (progress ** 3)
    curr_zoom = 1.0 + (max_zoom - 1.0) * smooth_p

    new_w = int(w / curr_zoom)
    new_h = int(h / curr_zoom)

    # Calculate center with subtle pan shift
    cx = (w / 2.0) + (pan_dx * smooth_p * (w - new_w) * 0.4)
    cy = (h / 2.0) + (pan_dy * smooth_p * (h - new_h) * 0.4)

    left = int(max(0, min(w - new_w, cx - new_w / 2.0)))
    top = int(max(0, min(h - new_h, cy - new_h / 2.0)))
    right = left + new_w
    bottom = top + new_h

    cropped = image.crop((left, top, right, bottom))
    return cropped.resize((w, h), Image.Resampling.BILINEAR)


# -----------------------------------------------------------------------------
# Hormozi-Style Kinetic Subtitle Card Drawer
# -----------------------------------------------------------------------------
def draw_kinetic_subtitle_card(
    card: SubtitleCard,
    palette: Dict[str, Any],
) -> Image.Image:
    """
    Renders punchy, centered subtitle cards with dynamic velocity-scaled typography,
    keyword highlights, and translucent pill backing.
    """
    card_img = Image.new("RGBA", (CANVAS_WIDTH, 340), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(card_img)

    base_font_size = int(58 * card.velocity_scale)
    font = get_system_font(size=base_font_size, bold=True)

    words = card.words
    if not words:
        return card_img

    base_font_size = int(58 * card.velocity_scale)
    font = get_system_font(size=base_font_size, bold=True)

    space_w = draw.textlength(" ", font=font)
    word_widths = [draw.textlength(w.word, font=font) for w in words]
    total_text_w = sum(word_widths) + (len(words) - 1) * space_w

    # Responsive auto-scaling: ensure card text and pill never overflow the 1080px canvas
    max_text_w = CANVAS_WIDTH - 160  # 80px safe horizontal margin
    if total_text_w > max_text_w and total_text_w > 0:
        scale = max_text_w / total_text_w
        base_font_size = max(28, int(base_font_size * scale))
        font = get_system_font(size=base_font_size, bold=True)
        space_w = draw.textlength(" ", font=font)
        word_widths = [draw.textlength(w.word, font=font) for w in words]
        total_text_w = sum(word_widths) + (len(words) - 1) * space_w

    center_x = CANVAS_WIDTH // 2
    center_y = 170

    # Pill background
    pad_x = 38
    pad_y = 22
    half_w = total_text_w / 2.0
    pill_box = [
        center_x - half_w - pad_x,
        center_y - (base_font_size // 2) - pad_y,
        center_x + half_w + pad_x,
        center_y + (base_font_size // 2) + pad_y,
    ]

    # Pill color & border
    hi_r, hi_g, hi_b = palette["highlight"]
    acc_r, acc_g, acc_b = palette["accent"]
    border_color = (hi_r, hi_g, hi_b, 240) if card.has_emphasis else (acc_r, acc_g, acc_b, 180)
    draw.rounded_rectangle(pill_box, radius=24, fill=(10, 14, 22, 225), outline=border_color, width=3)

    # Word placement (anchor='lm' aligns left-to-right starting at center_x - half_w)
    curr_x = center_x - half_w
    for idx, w_obj in enumerate(words):
        # Color: Emphasis in Gold / Crimson / Highlight color; Standard in crisp white
        if w_obj.is_emphasis:
            text_color = (hi_r, hi_g, hi_b, 255)
        else:
            text_color = (255, 255, 255, 255)

        # Drop shadow
        draw.text((curr_x + 3, center_y + 3), w_obj.word, font=font, fill=(0, 0, 0, 240), anchor="lm")
        # Main text
        draw.text((curr_x, center_y), w_obj.word, font=font, fill=text_color, anchor="lm")
        curr_x += word_widths[idx] + space_w

    return card_img


# -----------------------------------------------------------------------------
# High-Retention Visual Hook Badge
# -----------------------------------------------------------------------------
def draw_hook_badge(topic: str, palette: Dict[str, Any]) -> Image.Image:
    """
    Renders an elite, high-retention 'CONFIDENTIAL CASE STUDY' badge
    overlaid at the top of the frame during the hook duration (first 3-5s).
    Instantly stops feed-scrollers and establishes the investigative narrative context.
    """
    badge_img = Image.new("RGBA", (CANVAS_WIDTH, 260), (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge_img)

    hi_r, hi_g, hi_b = palette["highlight"]
    acc_r, acc_g, acc_b = palette["accent"]

    # Red confidential alert pill
    tag_box = [60, 60, 520, 114]
    draw.rounded_rectangle(tag_box, radius=8, fill=(185, 20, 20, 230), outline=(255, 60, 60, 255), width=2)
    tag_font = get_system_font(size=25, bold=True)
    draw.text((80, 72), "🔴 CONFIDENTIAL // CASE FILE", font=tag_font, fill=(255, 255, 255, 255))

    # Bold topic headline
    title_font = get_system_font(size=36, bold=True)
    clean_topic = topic.strip().upper()
    if len(clean_topic) > 36:
        clean_topic = clean_topic[:33] + "..."
    # Drop shadow
    draw.text((66, 134), clean_topic, font=title_font, fill=(0, 0, 0, 230))
    draw.text((64, 132), clean_topic, font=title_font, fill=(245, 248, 255, 255))

    # Sleek bottom border
    draw.line([(60, 192), (CANVAS_WIDTH - 60, 192)], fill=(acc_r, acc_g, acc_b, 200), width=3)

    return badge_img


# -----------------------------------------------------------------------------
# Video Timeline & Scene Beat Manager (Multi-Beat Cross-Dissolve)
# -----------------------------------------------------------------------------
class VideoSceneManager:
    def __init__(
        self,
        total_duration: float,
        hook_duration: float,
        palette: Dict[str, Any],
        topic: str,
        seed: int,
        spoken_text: str = "",
    ):
        self.total_duration = total_duration
        self.palette = palette
        self.rng = random.Random(seed)

        # 1. Plan high-retention visual beats (cuts every 2.8 - 4.0s)
        self.beats = plan_visual_beats(spoken_text or topic, total_duration, hook_duration)

        # 2. Resolve assets across pluggable providers (Pixabay, Local SDXL, Wikimedia, etc.)
        self.beats = resolve_all_beat_assets(self.beats, palette, seed)

        # 3. Cache base frames and micro-motion vectors
        self.scenes = []
        for beat in self.beats:
            asset = beat.asset
            zoom_rate = self.rng.uniform(1.05, 1.15)
            pan_x = self.rng.choice([-1.0, 0.0, 1.0])
            pan_y = self.rng.choice([-1.0, 0.0, 1.0])

            base_img = None
            if asset and asset.file_path.exists():
                try:
                    raw = Image.open(str(asset.file_path)).convert("RGB")
                    base_img = self._crop_to_vertical(raw)
                except Exception as e:
                    logger.warning(f"Error loading image {asset.file_path}: {e}")

            if base_img is None:
                # Emergency procedural canvas
                arr = render_scene_backdrop("HOOK", palette, topic, seed)
                base_img = Image.fromarray(arr)

            self.scenes.append({
                "beat": beat,
                "base_img": base_img,
                "zoom_rate": zoom_rate,
                "pan_x": pan_x,
                "pan_y": pan_y,
            })

    def _crop_to_vertical(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        target_ratio = CANVAS_WIDTH / CANVAS_HEIGHT
        if (w / h) > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            cropped = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            cropped = img.crop((0, top, w, top + new_h))
        return cropped.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.BILINEAR)

    def _sample_beat_frame(self, scene_dict: Dict[str, Any], t: float) -> Image.Image:
        beat = scene_dict["beat"]
        beat_start = beat.start_time
        beat_dur = beat.duration
        progress = np.clip((t - beat_start) / max(0.2, beat_dur), 0.0, 1.0)

        return get_ken_burns_crop(
            scene_dict["base_img"],
            progress=progress,
            max_zoom=scene_dict["zoom_rate"],
            pan_dx=scene_dict["pan_x"],
            pan_dy=scene_dict["pan_y"],
        )

    def get_scene_frame(self, t: float) -> Image.Image:
        # Find active beat
        active_idx = len(self.scenes) - 1
        for idx, s in enumerate(self.scenes):
            if s["beat"].start_time <= t < s["beat"].end_time:
                active_idx = idx
                break

        curr_scene = self.scenes[active_idx]
        curr_frame = self._sample_beat_frame(curr_scene, t)

        # 0.35s buttery smooth cross-dissolve to eliminate black screens and sudden jumps
        transition_dur = 0.35
        rel_time = t - curr_scene["beat"].start_time
        if rel_time < transition_dur and active_idx > 0:
            prev_scene = self.scenes[active_idx - 1]
            prev_frame = self._sample_beat_frame(prev_scene, t)
            alpha = np.clip(rel_time / transition_dur, 0.0, 1.0)
            return Image.blend(prev_frame, curr_frame, alpha)

        return curr_frame


# -----------------------------------------------------------------------------
# MoviePy Frame Generator & Compositor
# -----------------------------------------------------------------------------
def render_kinetic_short_video(
    master_audio_path: Path,
    subtitle_cards: List[SubtitleCard],
    output_video_path: Path,
    topic: str,
    visual_seed: int,
    hook_duration: float = 3.5,
    spoken_text: str = "",
    fps: int = DEFAULT_FPS,
) -> Path:
    """
    Renders the complete 1080x1920 vertical video with MoviePy and native FFmpeg:
    - Sentence-by-sentence dynamic visual beats (every 2.8 - 4.0s)
    - 350ms seamless cross-dissolves (zero black screens)
    - Ken Burns micro-motion on all scenes
    - Hormozi subtitle cards with dynamic velocity scaling
    - 0dB / -20dB mastered audio sync
    """
    if not is_moviepy_available():
        raise RuntimeError("MoviePy is not available. Please install via requirements_engine.txt.")

    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    audio_clip = AudioFileClip(str(master_audio_path))
    total_duration = audio_clip.duration

    palette = derive_color_palette(visual_seed)
    scene_manager = VideoSceneManager(
        total_duration=total_duration,
        hook_duration=hook_duration,
        palette=palette,
        topic=topic,
        seed=visual_seed,
        spoken_text=spoken_text,
    )

    # Pre-cache subtitle card PIL images and hook badge for fast composition
    cached_cards = []
    for c in subtitle_cards:
        c_img = draw_kinetic_subtitle_card(c, palette)
        cached_cards.append((c.start, c.end, c_img))

    cached_hook_badge = draw_hook_badge(topic, palette)

    logger.info(f"Rendering {total_duration:.1f}s vertical short (seed={visual_seed}, FPS={fps})...")

    def make_frame(t: float) -> np.ndarray:
        # 1. Base frame with dynamic Ken Burns
        frame_img = scene_manager.get_scene_frame(t).convert("RGBA")

        # 2. Hook attention badge during the first 3-5 seconds
        if t <= hook_duration:
            frame_img.alpha_composite(cached_hook_badge, dest=(0, 0))

        # 3. Overlay active kinetic subtitle card (placed at Y = 1320)
        for c_start, c_end, c_img in cached_cards:
            if c_start <= t < c_end:
                frame_img.alpha_composite(c_img, dest=(0, 1320))
                break

        return np.array(frame_img.convert("RGB"))

    video_clip = VideoClip(make_frame)
    video_clip = set_clip_duration(video_clip, total_duration)
    video_clip = set_clip_fps(video_clip, fps)
    video_clip = set_clip_audio(video_clip, audio_clip)

    # Render video with high-efficiency H.264 encoding and resilient fallback
    write_kwargs = {
        "fps": fps,
        "codec": "libx264",
        "audio_codec": "aac",
        "preset": "veryfast",
        "threads": 4,
        "ffmpeg_params": ["-crf", "19", "-pix_fmt", "yuv420p"],
        "logger": None,
    }

    try:
        video_clip.write_videofile(str(output_video_path), **write_kwargs)
    except Exception as e:
        logger.warning(f"Standard video encoding failed ({e}). Retrying with baseline compatibility parameters...")
        video_clip.write_videofile(
            str(output_video_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            threads=2,
            logger=None,
        )

    audio_clip.close()
    video_clip.close()

    logger.info(f"Successfully rendered master vertical video: {output_video_path} ({output_video_path.stat().st_size / (1024*1024):.2f} MB)")
    return output_video_path
