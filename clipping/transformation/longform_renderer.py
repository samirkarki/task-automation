"""
Long-Form Compilation Renderer.
Concatenates multiple clip segments into a single 8-10 minute 1920x1080 16:9 MP4.

Ordering: hype-ranked ASCENDING (best clip last = save-the-best-for-last retention).
Includes: intro bumper, numbered segment title cards, fade transitions, outro bumper,
          royalty-free background music, EBU R128 loudness normalization.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger("clipping.transformation.longform_renderer")

try:
    from common.whisper_utils import ensure_ffmpeg_on_path
    ensure_ffmpeg_on_path()
except Exception:
    pass

# User-provided royalty-free music goes here (MP3/WAV/OGG/M4A)
_BUNDLED_MUSIC_DIR = Path(__file__).parent.parent / "data" / "music"


def _get_royalty_free_track() -> Optional[Path]:
    """
    Returns first royalty-free audio track found in clipping/data/music/.
    Returns None if no tracks are present (music overlay is skipped).
    """
    if _BUNDLED_MUSIC_DIR.exists():
        for ext in ["mp3", "wav", "ogg", "m4a"]:
            for f in sorted(_BUNDLED_MUSIC_DIR.glob(f"*.{ext}")):
                logger.info(f"Using royalty-free track: {f.name}")
                return f
    logger.info(
        "No royalty-free tracks found in clipping/data/music/ — "
        "game audio will be normalised as-is."
    )
    return None


def _get_video_duration(path: Path) -> float:
    """Returns video duration in seconds using ffprobe."""
    try:
        res = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def _normalize_clip_to_1080p(
    input_path: Path,
    output_path: Path,
    mute_game_music: bool = True,
) -> bool:
    """
    Scales a clip to exactly 1920x1080 (letterboxed if needed).
    Returns True on success.
    """
    af = (
        "highpass=f=200,loudnorm=I=-14:LRA=9:TP=-1.0"
        if mute_game_music
        else "loudnorm=I=-14:LRA=9:TP=-1.0"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", (
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black"
        ),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-af", af,
        "-movflags", "+faststart",
        str(output_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if res.returncode != 0:
        logger.warning(
            f"Normalize clip failed for {input_path.name}: {res.stderr[:200]}"
        )
        return False
    return True


def _render_title_card(
    title: str,
    subtitle: str,
    output_path: Path,
    accent_color: str = "0x00FFFF",
    duration: float = 3.0,
) -> bool:
    """
    Renders a 3-second 1920x1080 title card using FFmpeg drawtext.
    Returns True on success.
    """
    # Convert "0xRRGGBB" → "#RRGGBB" for FFmpeg drawtext
    accent_hex = "#" + accent_color.replace("0x", "").replace("#", "")

    # Escape single quotes in text
    safe_title = title.replace("'", "").replace(":", " -").replace("\\", "")
    safe_subtitle = subtitle.replace("'", "").replace(":", " -").replace("\\", "")

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x0A0A14:size=1920x1080:rate=25",
        "-t", str(duration),
        "-vf", (
            f"drawtext=text='{safe_title}':fontsize=72:fontcolor=white"
            f":x=(w-text_w)/2:y=(h-text_h)/2-40,"
            f"drawtext=text='{safe_subtitle}':fontsize=42"
            f":fontcolor={accent_hex}"
            f":x=(w-text_w)/2:y=(h-text_h)/2+60,"
            f"fade=t=in:st=0:d=0.3,"
            f"fade=t=out:st={duration - 0.5:.2f}:d=0.5"
        ),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-an",
        str(output_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0:
        logger.warning(f"Title card render failed: {res.stderr[:200]}")
        return False
    return True


def render_longform_compilation(
    clip_paths: List[Path],
    clip_scores: List[float],
    output_path: Path,
    intro_bumper_path: Optional[Path] = None,
    outro_bumper_path: Optional[Path] = None,
    target_duration: float = 600.0,
    channel_brand_name: str = "ClipBot",
    game_title: str = "Gaming Highlights",
    accent_color: str = "0x00FFFF",
    mute_game_music: bool = True,
) -> Optional[Path]:
    """
    Assembles a long-form 1920x1080 MP4 compilation from pre-rendered clip segments.

    Args:
        clip_paths: List of raw video clip segment paths (any resolution).
        clip_scores: Hype scores for each clip (same order as clip_paths).
        output_path: Where to write the compiled MP4.
        intro_bumper_path: Optional 10s intro bumper MP4.
        outro_bumper_path: Optional 10s outro bumper MP4.
        target_duration: Soft target total duration in seconds (default 600 = 10 min).
        channel_brand_name: Brand name for segment title cards.
        game_title: Game title displayed on title cards.
        accent_color: Hex color for title card accent (e.g. "0x00FFFF").
        mute_game_music: If True, apply high-pass filter to suppress in-game music.

    Returns:
        Path to compiled MP4, or None on failure.
    """
    if not clip_paths:
        logger.warning("No clip paths provided for long-form compilation.")
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Sort clips ASCENDING by hype score (best clip last) ---
    paired = list(zip(clip_scores, clip_paths))
    paired_valid = [(s, p) for s, p in paired if Path(p).exists()]
    if not paired_valid:
        logger.error("No valid clip files found on disk for long-form compilation.")
        return None

    paired_sorted = sorted(paired_valid, key=lambda x: x[0])  # ascending = best last
    ordered_clips: List[Tuple[float, Path]] = paired_sorted

    total_clip_dur = sum(_get_video_duration(p) for _, p in ordered_clips)
    logger.info(
        f"Long-form: {len(ordered_clips)} clips, "
        f"raw duration={total_clip_dur:.0f}s, target={target_duration:.0f}s"
    )
    if total_clip_dur < target_duration * 0.5:
        logger.warning(
            f"Total clip duration ({total_clip_dur:.0f}s) < 50% of target "
            f"({target_duration:.0f}s). Run pipeline with more --clips for a fuller compilation."
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        segment_files: List[Path] = []

        # --- Intro bumper ---
        if intro_bumper_path and intro_bumper_path.exists():
            segment_files.append(intro_bumper_path)

        # --- Per-clip: title card + normalised clip ---
        for idx, (score, clip_path) in enumerate(ordered_clips, start=1):
            is_last = idx == len(ordered_clips)
            label = f"Clip #{idx}" + (" \U0001f525 BEST MOMENT" if is_last else "")

            title_card_path = tmp / f"title_{idx}.mp4"
            if _render_title_card(
                title=label,
                subtitle=game_title,
                output_path=title_card_path,
                accent_color=accent_color,
                duration=3.0,
            ):
                segment_files.append(title_card_path)

            norm_clip = tmp / f"clip_{idx}_norm.mp4"
            if _normalize_clip_to_1080p(clip_path, norm_clip, mute_game_music=mute_game_music):
                segment_files.append(norm_clip)

        # --- Outro bumper ---
        if outro_bumper_path and outro_bumper_path.exists():
            segment_files.append(outro_bumper_path)

        if not segment_files:
            logger.error("No segment files built — aborting long-form render.")
            return None

        # --- Write FFmpeg concat list ---
        concat_txt = tmp / "concat.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for seg in segment_files:
                # FFmpeg concat demuxer: escape backslashes and single quotes
                escaped = str(seg).replace("\\", "/").replace("'", "\\'")
                f.write(f"file '{escaped}'\n")

        logger.info(f"Concat list built: {len(segment_files)} segments")

        # --- FFmpeg concat + audio mixing ---
        music_track = _get_royalty_free_track()

        if music_track:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_txt),
                "-stream_loop", "-1",
                "-i", str(music_track),
                "-map", "0:v",
                "-filter_complex",
                (
                    "[0:a]volume=0.3[game];"
                    "[1:a]volume=0.7[music];"
                    "[game][music]amix=inputs=2:duration=first[aout];"
                    "[aout]loudnorm=I=-14:LRA=9:TP=-1.0[afinal]"
                ),
                "-map", "[afinal]",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "19",
                "-c:a", "aac",
                "-b:a", "256k",
                "-movflags", "+faststart",
                str(output_path),
            ]
        else:
            af_chain = "loudnorm=I=-14:LRA=9:TP=-1.0"
            if mute_game_music:
                af_chain = "highpass=f=200,equalizer=f=3200:t=q:w=1.2:g=3.0," + af_chain

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_txt),
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "19",
                "-c:a", "aac",
                "-b:a", "256k",
                "-af", af_chain,
                "-movflags", "+faststart",
                str(output_path),
            ]

        logger.info(f"Rendering long-form compilation → {output_path.name} ...")
        res = subprocess.run(cmd, capture_output=True, text=True)

    if res.returncode != 0:
        logger.error(f"Long-form FFmpeg render failed: {res.stderr[:600]}")
        return None

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    actual_dur = _get_video_duration(output_path)
    logger.info(
        f"Long-form compilation complete: {output_path.name} "
        f"({actual_dur:.0f}s / {file_size_mb:.1f} MB)"
    )
    return output_path
