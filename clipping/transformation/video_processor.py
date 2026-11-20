"""
High-Performance Transformative Video Processor.
Renders broadcast-grade 1080x1920 60fps vertical Shorts with:
1. Smart Split-Screen (Streamer Facecam Top + Centered Gameplay Bottom)
2. Dynamic Action Framing (MrBeast style)
3. Word-by-word animated ASS subtitles
4. Top curiosity hook banner
5. Anti-copyright vocal boost and in-game radio music filtering
6. EBU R128 (-14 LUFS) loudness normalization
"""

import logging
from pathlib import Path
import subprocess
from typing import Any, Dict, Optional, Union

from clipping.config import (
    COLOR_GRADE_HUE_SHIFT,
    COLOR_GRADE_SAT_BOOST,
    MAX_CLIP_DURATION,
)
from clipping.models import ClipCandidate
from clipping.profiles.base import ClipProfile
from clipping.profiles import DEFAULT_PROFILE
from clipping.transformation.facecam_detector import FacecamDetector

try:
    from common.whisper_utils import ensure_ffmpeg_on_path
    ensure_ffmpeg_on_path()
except Exception:
    pass

logger = logging.getLogger("clipping.transformation.video_processor")


def escape_ffmpeg_path(path: Path) -> str:
    """Escapes Windows path for FFmpeg filter syntax."""
    p_str = str(path.resolve()).replace("\\", "/")
    p_str = p_str.replace(":", "\\:")
    return p_str


def build_split_screen_filter_graph(
    facecam_coords: Dict[str, Any],
    split_ratio: float,
    escaped_sub: str,
    clean_hook: str,
    divider_color: str = "0x00FFFF",  # Cyan accent for divider
) -> str:
    """
    Constructs an FFmpeg filter_complex graph for Smart Split-Screen:
      [0:v] split into [cam_in] and [game_in]
      [cam_in] cropped to facecam, scaled to 1080:top_h -> [cam_out]
      [game_in] center-cropped to gameplay, scaled to 1080:bottom_h -> [game_out]
      [cam_out][game_out] vstack -> [stacked]
      [stacked] add neon divider + burn subtitles + hook banner -> [vout]
    """
    total_h = 1920
    top_h = int(round(total_h * split_ratio))
    # Ensure even dimensions for libx264
    if top_h % 2 != 0:
        top_h += 1
    bottom_h = total_h - top_h

    fx = facecam_coords.get("x", 1440)
    fy = facecam_coords.get("y", 680)
    fw = facecam_coords.get("w", 480)
    fh = facecam_coords.get("h", 400)

    # Divider bar thickness: 6px
    div_y = top_h - 3

    # Build filter complex
    fc_filter = (
        f"[0:v]split=2[cam_raw][game_raw];"
        # Facecam branch: crop to facecam box, scale to 1080:top_h, slight saturation boost
        f"[cam_raw]crop={fw}:{fh}:{fx}:{fy},scale=1080:{top_h}:force_original_aspect_ratio=increase,"
        f"crop=1080:{top_h},hue=s=1.06[cam_out];"
        # Gameplay branch: centered crop, scale to 1080:bottom_h
        f"[game_raw]crop=ih*(1080/{bottom_h}):ih,scale=1080:{bottom_h},hue=h={COLOR_GRADE_HUE_SHIFT}:s={COLOR_GRADE_SAT_BOOST}[game_out];"
        # Stack vertically
        f"[cam_out][game_out]vstack=inputs=2[stacked];"
        # Neon divider line
        f"[stacked]drawbox=x=0:y={div_y}:w=1080:h=6:color={divider_color}@0.95:t=fill,"
        # Burn animated karaoke subtitles
        f"subtitles='{escaped_sub}',"
        # Curiosity hook title banner at top (first 3.8s)
        f"drawtext=text='{clean_hook}':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.7:boxborderw=18:"
        f"x=(w-text_w)/2:y=180:enable='between(t,0,3.8)'[vout]"
    )
    return fc_filter


def build_action_crop_filter_graph(
    escaped_sub: str,
    clean_hook: str,
) -> str:
    """
    Constructs an FFmpeg filter chain for 9:16 Action Framing (MrBeast style).
    """
    vf = (
        f"crop=ih*(9/16):ih,"
        f"scale=1080:1920,"
        f"hue=h={COLOR_GRADE_HUE_SHIFT}:s={COLOR_GRADE_SAT_BOOST},"
        f"subtitles='{escaped_sub}',"
        f"drawtext=text='{clean_hook}':fontcolor=white:fontsize=50:box=1:boxcolor=black@0.65:boxborderw=18:"
        f"x=(w-text_w)/2:y=220:enable='between(t,0,3.8)'"
    )
    return vf


def render_transformed_short(
    source_video: Path,
    clip: ClipCandidate,
    master_audio: Optional[Path],
    subtitle_file: Path,
    hook_title: str,
    output_path: Path,
    profile: Optional[ClipProfile] = None,
) -> Path:
    """
    Renders high-bitrate 1080x1920 MP4 vertical Short with profile-driven layout.
    """
    prof = profile or DEFAULT_PROFILE
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = min(clip.duration, float(prof.max_clip_duration))
    escaped_sub = escape_ffmpeg_path(subtitle_file)

    clean_hook = hook_title.replace("'", "").replace('"', "").replace(":", " -")[:42]

    # Audio filter chain: EBU R128 loudness normalization + vocal presence EQ to duck background music
    if prof.duck_background_music:
        # Highpass 85Hz removes sub-bass radio rumble, 3kHz vocal presence boost
        af_chain = "highpass=f=85,equalizer=f=3200:t=q:w=1.2:g=2.5,loudnorm=I=-14:LRA=9:TP=-1.0"
    else:
        af_chain = "loudnorm=I=-14:LRA=9:TP=-1.0"

    use_custom_audio = master_audio is not None and Path(master_audio).exists()

    seek_time = "0.0" if clip.is_pre_cut else str(clip.start_sec)
    facecam_sample_t = 2.0 if clip.is_pre_cut else (clip.start_sec + 2.0)

    # Determine layout mode
    is_split_screen = prof.layout_mode == "smart_split_screen"

    if is_split_screen:
        # Detect facecam coordinates
        detector = FacecamDetector()
        facecam_coords = detector.detect_facecam_crop(source_video, sample_time_sec=facecam_sample_t)
        filter_complex = build_split_screen_filter_graph(
            facecam_coords=facecam_coords,
            split_ratio=prof.split_ratio,
            escaped_sub=escaped_sub,
            clean_hook=clean_hook,
            divider_color="0x00FFFF" if prof.name == "game-gta6" else "0xFFFF00",
        )

        cmd = [
            "ffmpeg", "-y",
            "-ss", seek_time,
            "-i", str(source_video),
        ]
        if use_custom_audio:
            cmd.extend(["-i", str(master_audio)])

        cmd.extend([
            "-t", str(duration),
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "1:a" if use_custom_audio else "0:a",
            "-c:v", "libx264",
            "-preset", "medium",  # Upgraded from veryfast for crisp 60fps quality
            "-crf", "19",          # Upgraded from 22 for broadcast fidelity
            "-c:a", "aac",
            "-b:a", "256k",        # Upgraded from 192k
            "-af", af_chain,
            "-movflags", "+faststart",
            str(output_path),
        ])

    else:
        # Action Crop (e.g. MrBeast) or Single Speaker
        vf_chain = build_action_crop_filter_graph(escaped_sub=escaped_sub, clean_hook=clean_hook)
        cmd = [
            "ffmpeg", "-y",
            "-ss", seek_time,
            "-i", str(source_video),
        ]
        if use_custom_audio:
            cmd.extend(["-i", str(master_audio)])

        cmd.extend([
            "-t", str(duration),
            "-vf", vf_chain,
            "-map", "0:v",
            "-map", "1:a" if use_custom_audio else "0:a",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "19",
            "-c:a", "aac",
            "-b:a", "256k",
            "-af", af_chain,
            "-movflags", "+faststart",
            str(output_path),
        ])

    logger.info(
        f"Rendering {prof.display_name} Short: {output_path.name} "
        f"[{prof.layout_mode}] (duration={duration:.1f}s)..."
    )

    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

    if res.returncode != 0:
        logger.warning(
            f"FFmpeg primary render returned error ({res.stderr[:200]}). "
            "Falling back to streamlined vertical render..."
        )
        # Robust fallback filter
        fallback_vf = (
            f"crop=ih*(9/16):ih,scale=1080:1920,"
            f"hue=h={COLOR_GRADE_HUE_SHIFT}:s={COLOR_GRADE_SAT_BOOST}"
        )
        fallback_cmd = [
            "ffmpeg", "-y",
            "-ss", str(clip.start_sec),
            "-i", str(source_video),
            "-t", str(duration),
            "-vf", fallback_vf,
            "-map", "0:v",
            "-map", "0:a" if not use_custom_audio else "1:a",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "21",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path),
        ]
        if use_custom_audio:
            fallback_cmd.insert(6, "-i")
            fallback_cmd.insert(7, str(master_audio))

        fb_res = subprocess.run(fallback_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if fb_res.returncode != 0:
            raise RuntimeError(f"FFmpeg rendering failed: {fb_res.stderr}")

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(f"Broadcast Short successfully rendered: {output_path.name} ({file_size_mb:.2f} MB)")
    return output_path
