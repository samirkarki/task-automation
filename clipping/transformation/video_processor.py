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


def build_floating_pip_filter_graph(
    facecam_coords: Dict[str, Any],
    escaped_sub: str,
    clean_hook: str,
    border_color: str = "0x00FFFF",  # Cyan accent default (0xFFFF00 for Fortnite)
    gameplay_y: int = 360,
    pip_x: int = 50,
    pip_y: int = 1420,
    pip_w: int = 340,
    pip_h: int = 255,
) -> str:
    """
    Constructs an FFmpeg filter_complex graph for Floating Corner PiP:
      1. Background: Sourced from gameplay, scaled to 1080x1920 with boxblur=25:5 and -15% brightness.
      2. Foreground: Uncropped 16:9 gameplay scaled to 1080x608, placed at gameplay_y (default 360).
      3. Streamer PiP (when has_facecam is True):
         - Cropped to streamer quadrant, scaled to pip_w x pip_h (default 340x255).
         - Overlaid at bottom-left pip_x, pip_y (default x=50, y=1420) with a 3px neon border.
         - Substantially marginalized (~15% of screen), leaving gameplay uncompromised!
      4. Zero Empty-Box Fallback (when has_facecam is False):
         - Webcam badge is completely omitted! Renders full-screen gameplay with ambient blur.
      5. Subtitles & Hook:
         - Word-by-word karaoke subtitles centered at y ≈ 1160 (safe from PiP and center gameplay).
         - Curiosity hook banner at top (y=180, first 3.8s).
    """
    has_cam = facecam_coords.get("has_facecam", False)
    fx = facecam_coords.get("x", 0)
    fy = facecam_coords.get("y", 0)
    fw = facecam_coords.get("w", 0)
    fh = facecam_coords.get("h", 0)

    # Subtitle and hook overlay filter chain
    sub_and_hook = (
        f"subtitles='{escaped_sub}',"
        f"drawtext=text='{clean_hook}':fontcolor=white:fontsize=48:box=1:boxcolor=black@0.7:boxborderw=18:"
        f"x=(w-text_w)/2:y=180:enable='between(t,0,3.8)'[vout]"
    )

    if has_cam and fw > 0 and fh > 0:
        fc_filter = (
            f"[0:v]split=3[bg_src][game_src][cam_src];"
            # Background ambient blur
            f"[bg_src]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"boxblur=25:5,eq=brightness=-0.15[bg_blur];"
            # Uncropped 16:9 gameplay
            f"[game_src]scale=1080:608:force_original_aspect_ratio=decrease,"
            f"hue=h={COLOR_GRADE_HUE_SHIFT}:s={COLOR_GRADE_SAT_BOOST}[game_sharp];"
            # Overlay gameplay in upper-mid
            f"[bg_blur][game_sharp]overlay=0:{gameplay_y}[base];"
            # Streamer reaction PiP badge with neon border
            f"[cam_src]crop={fw}:{fh}:{fx}:{fy},scale={pip_w}:{pip_h},"
            f"drawbox=x=0:y=0:w={pip_w}:h={pip_h}:color={border_color}@0.95:t=3,hue=s=1.06[cam_badge];"
            # Overlay streamer PiP in bottom-left corner
            f"[base][cam_badge]overlay={pip_x}:{pip_y}[comp];"
            f"[comp]{sub_and_hook}"
        )
    else:
        fc_filter = (
            f"[0:v]split=2[bg_src][game_src];"
            # Background ambient blur
            f"[bg_src]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"boxblur=25:5,eq=brightness=-0.15[bg_blur];"
            # Uncropped 16:9 gameplay
            f"[game_src]scale=1080:608:force_original_aspect_ratio=decrease,"
            f"hue=h={COLOR_GRADE_HUE_SHIFT}:s={COLOR_GRADE_SAT_BOOST}[game_sharp];"
            # Overlay gameplay in upper-mid
            f"[bg_blur][game_sharp]overlay=0:{gameplay_y}[base];"
            # Burn animated subtitles + hook banner directly on base
            f"[base]{sub_and_hook}"
        )
    return fc_filter


def build_split_screen_filter_graph(
    facecam_coords: Dict[str, Any],
    split_ratio: float,
    escaped_sub: str,
    clean_hook: str,
    divider_color: str = "0x00FFFF",  # Cyan accent for divider
) -> str:
    """
    Backwards compatibility alias for build_floating_pip_filter_graph.
    Directs split-screen rendering to the upgraded Floating Corner PiP layout.
    """
    coords = dict(facecam_coords)
    if "has_facecam" not in coords:
        coords["has_facecam"] = coords.get("w", 0) > 0 and coords.get("h", 0) > 0
    return build_floating_pip_filter_graph(
        facecam_coords=coords,
        escaped_sub=escaped_sub,
        clean_hook=clean_hook,
        border_color=divider_color,
    )


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
    is_split_screen = prof.layout_mode in ("smart_split_screen", "floating_pip")

    if is_split_screen:
        # Detect facecam coordinates with multi-corner consensus
        detector = FacecamDetector()
        facecam_coords = detector.detect_facecam_crop(source_video, sample_time_sec=facecam_sample_t)
        filter_complex = build_floating_pip_filter_graph(
            facecam_coords=facecam_coords,
            escaped_sub=escaped_sub,
            clean_hook=clean_hook,
            border_color="0x00FFFF" if prof.name == "game-gta6" else "0xFFFF00",
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
