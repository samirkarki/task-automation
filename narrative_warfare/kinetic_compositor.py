#!/usr/bin/env python3
"""
Kinetic Media Compositor (MoviePy & Native FFmpeg)
Renders high-retention 1080x1920 (9:16) vertical MP4 videos:
- Live-action stock video frame sampling with looping and Ken Burns micro-motion
- Zero black screens: pre-cached poster frames & 350ms buttery cross-dissolves
- Responsive velocity-scaled Hormozi-style subtitle cards with auto-scaling
- Elite 'CONFIDENTIAL CASE STUDY' hook badge for immediate retention
- Frame-by-frame kinetic variation breaking platform duplicate fingerprinting
- Mastered audio track attachment (0dB voice + -20dB ambient drone)
- Full resource cleanup releasing all open file descriptors
"""

import os
import io
import sys
import math
import random
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from common.env_loader import load_project_env

# Guarantee environment variables from .env are loaded
load_project_env()

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
from common.moviepy_compat import (
    VideoClip,
    VideoFileClip,
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
    Applies continuous, cinematic Ken Burns zoom and slow pan across time progress [0.0 -> 1.0].
    Guarantees output image dimensions are strictly (CANVAS_WIDTH, CANVAS_HEIGHT).
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    w, h = image.size
    zoom = 1.0 + (max_zoom - 1.0) * progress

    # Current zoomed sub-window dimensions
    new_w = int(w / zoom)
    new_h = int(h / zoom)

    # Offset ranges
    max_dx = w - new_w
    max_dy = h - new_h

    # Normalized directional pan
    offset_x = int((max_dx / 2.0) + (pan_dx * (max_dx / 2.0) * (progress - 0.5) * 2.0))
    offset_y = int((max_dy / 2.0) + (pan_dy * (max_dy / 2.0) * (progress - 0.5) * 2.0))

    left = np.clip(offset_x, 0, max_dx)
    top = np.clip(offset_y, 0, max_dy)
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
    keyword highlights, and translucent pill backing. Auto-scales font to prevent edge clipping.
    """
    card_img = Image.new("RGBA", (CANVAS_WIDTH, 340), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(card_img)

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
        # Color: Emphasis in Highlight color; Standard in crisp white
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
# Video Timeline & Scene Beat Manager (Multi-Beat Cross-Dissolve & Video Clips)
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

        # 1. Plan high-retention visual beats (cuts every 2.5 - 3.8s)
        self.beats = plan_visual_beats(spoken_text or topic, total_duration, hook_duration)

        # 2. Resolve assets across pluggable providers (Pixabay, Local SDXL, Pexels, Wikimedia, etc.)
        self.beats = resolve_all_beat_assets(self.beats, palette, seed)

        # 3. Cache base frames, video handles, and micro-motion vectors
        self.scenes = []
        for beat in self.beats:
            asset = beat.asset
            zoom_rate = self.rng.uniform(1.04, 1.10)
            pan_x = self.rng.choice([-0.7, 0.0, 0.7])
            pan_y = self.rng.choice([-0.7, 0.0, 0.7])

            video_clip = None
            base_img = None

            if asset and asset.file_path.exists():
                if asset.media_type == "video":
                    if VideoFileClip is not None:
                        try:
                            # Open live stock MP4 via MoviePy VideoFileClip
                            vclip = VideoFileClip(str(asset.file_path))
                            # Sample early poster frame (0.3s or 15% into clip)
                            t_poster = min(0.4, max(0.0, (getattr(vclip, 'duration', 5.0) or 5.0) * 0.15))
                            raw_frame = vclip.get_frame(t_poster)
                            base_img = self._crop_to_vertical(Image.fromarray(raw_frame))
                            video_clip = vclip
                            logger.info(f"[SCENE MANAGER] Live stock video active for Beat {beat.index+1}: {asset.file_path.name}")
                        except Exception as e:
                            logger.warning(f"Failed to open video {asset.file_path} via MoviePy: {e}. Trying FFmpeg fallback...")
                            base_img = self._extract_ffmpeg_frame(asset.file_path)
                    else:
                        base_img = self._extract_ffmpeg_frame(asset.file_path)
                else:
                    # Media type is static image
                    try:
                        raw = Image.open(str(asset.file_path)).convert("RGB")
                        base_img = self._crop_to_vertical(raw)
                    except Exception as e:
                        logger.warning(f"Error loading image {asset.file_path}: {e}")

            if base_img is None:
                # Emergency procedural canvas
                scene_type = ["HOOK", "CHESSBOARD", "ORDERBOOK", "TAKEOVER"][beat.index % 4]
                arr = render_scene_backdrop(scene_type, palette, topic, seed + beat.index * 17)
                base_img = Image.fromarray(arr)

            self.scenes.append({
                "beat": beat,
                "video_clip": video_clip,
                "base_img": base_img,
                "zoom_rate": zoom_rate,
                "pan_x": pan_x,
                "pan_y": pan_y,
            })

    def _crop_to_vertical(self, img: Image.Image) -> Image.Image:
        """Crops image to exact vertical 9:16 aspect ratio (1080x1920) centered."""
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        target_ratio = CANVAS_WIDTH / CANVAS_HEIGHT  # 0.5625
        current_ratio = w / h
        if current_ratio > target_ratio:
            # Wider than 9:16 -> crop left & right
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            cropped = img.crop((left, 0, left + new_w, h))
        else:
            # Taller than 9:16 -> crop top & bottom
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            cropped = img.crop((0, top, w, top + new_h))
        return cropped.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.BILINEAR)

    def _extract_ffmpeg_frame(self, file_path: Path) -> Optional[Image.Image]:
        """Extracts a poster frame via native FFmpeg subprocess when MoviePy fails to load video."""
        try:
            cmd = [
                "ffmpeg", "-y", "-ss", "00:00:01",
                "-i", str(file_path),
                "-vframes", "1",
                "-f", "image2pipe",
                "-vcodec", "png",
                "-"
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
            if proc.returncode == 0 and len(proc.stdout) > 1000:
                raw = Image.open(io.BytesIO(proc.stdout)).convert("RGB")
                return self._crop_to_vertical(raw)
        except Exception as e:
            logger.warning(f"FFmpeg poster extraction failed for {file_path}: {e}")
        return None

    def _sample_beat_frame(self, scene_dict: Dict[str, Any], t: float) -> Image.Image:
        """
        Samples the visual frame for the given beat at time t.
        If live stock video is loaded, extracts the frame dynamically with looping.
        Applies subtle Ken Burns micro-motion for continuous cinematic energy.
        """
        beat = scene_dict["beat"]
        beat_start = beat.start_time
        beat_dur = beat.duration
        progress = np.clip((t - beat_start) / max(0.2, beat_dur), 0.0, 1.0)

        vclip = scene_dict.get("video_clip")
        if vclip is not None:
            try:
                # Video is live! Calculate looping relative timestamp
                v_dur = max(0.5, (getattr(vclip, 'duration', 5.0) or 5.0) - 0.05)
                t_rel = (t - beat_start) % v_dur
                frame_arr = vclip.get_frame(t_rel)
                frame_img = Image.fromarray(frame_arr).convert("RGB")
                cropped = self._crop_to_vertical(frame_img)
                return get_ken_burns_crop(
                    cropped,
                    progress=progress,
                    max_zoom=scene_dict["zoom_rate"],
                    pan_dx=scene_dict["pan_x"] * 0.35,
                    pan_dy=scene_dict["pan_y"] * 0.35,
                )
            except Exception as e:
                logger.debug(f"Video frame sampling fallback to poster: {e}")

        # If static image or video fallback
        return get_ken_burns_crop(
            scene_dict["base_img"],
            progress=progress,
            max_zoom=scene_dict["zoom_rate"],
            pan_dx=scene_dict["pan_x"],
            pan_dy=scene_dict["pan_y"],
        )

    def get_scene_frame(self, t: float) -> Image.Image:
        """
        Returns the blended frame at timestamp t with smooth 350ms cross-dissolves
        between consecutive beats, eliminating black frames completely.
        """
        # Find active beat
        active_idx = len(self.scenes) - 1
        for idx, s in enumerate(self.scenes):
            if s["beat"].start_time <= t < s["beat"].end_time:
                active_idx = idx
                break

        curr_scene = self.scenes[active_idx]
        curr_frame = self._sample_beat_frame(curr_scene, t)

        # 0.35s buttery smooth cross-dissolve between beats
        transition_dur = 0.35
        rel_time = t - curr_scene["beat"].start_time
        if rel_time < transition_dur and active_idx > 0:
            prev_scene = self.scenes[active_idx - 1]
            prev_frame = self._sample_beat_frame(prev_scene, t)
            alpha = np.clip(rel_time / transition_dur, 0.0, 1.0)
            return Image.blend(prev_frame, curr_frame, alpha)

        return curr_frame

    def close(self):
        """Safely closes all open VideoFileClip instances to prevent file descriptor leaks."""
        for s in self.scenes:
            vclip = s.get("video_clip")
            if vclip is not None:
                try:
                    vclip.close()
                except Exception:
                    pass


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
    - Sentence-by-sentence dynamic visual beats (every 2.5 - 3.8s)
    - Real stock video clips with looping and Ken Burns motion
    - 350ms seamless cross-dissolves (zero black screens)
    - Hormozi subtitle cards with dynamic velocity scaling
    - 0dB / -20dB mastered audio sync
    - Guaranteed file descriptor cleanup
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
        # 1. Base frame with live stock video & Ken Burns
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
    finally:
        # Guarantee all audio, video, and scene handles are closed
        try:
            audio_clip.close()
        except Exception:
            pass
        try:
            video_clip.close()
        except Exception:
            pass
        scene_manager.close()

    logger.info(f"Successfully rendered master vertical video: {output_video_path} ({output_video_path.stat().st_size / (1024*1024):.2f} MB)")
    return output_video_path
