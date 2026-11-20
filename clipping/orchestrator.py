"""
Master Orchestrator for the Autonomous Multi-Profile YouTube Shorts Pipeline.
Coordinates Discovery -> Multi-Signal Extraction (Heatmap + Comments + Audio Spikes) ->
Faster-Whisper Transcription -> Contextual Boundary Expansion ->
Smart Split-Screen / Action Framing -> Metadata Generation -> YouTube Publishing.
"""

from datetime import datetime
import json
import logging
import os
from pathlib import Path
import subprocess
from typing import List, Optional, Tuple

from clipping.config import (
    CLIPS_PER_DAY,
    OUTPUT_DIR,
    GDRIVE_REMOTE,
)
from clipping.models import VideoMeta, ClipCandidate
from clipping.profiles import get_profile, DEFAULT_PROFILE
from clipping.profiles.base import ClipProfile
from clipping.discovery.searcher import search_niche_videos
from clipping.discovery.velocity_ranker import rank_by_velocity
from clipping.discovery.compliance_filter import ComplianceFilter
from clipping.extraction.heatmap import fetch_heatmap, find_peak_windows
from clipping.extraction.comment_miner import extract_comment_timestamp_peaks
from clipping.extraction.audio_peak_detector import analyze_audio_energy
from clipping.extraction.transcriber import transcribe_audio
from clipping.extraction.clip_selector import select_viral_clips
from clipping.transformation.commentary_writer import write_commentary
from clipping.transformation.tts_narrator import generate_narration
from clipping.transformation.subtitle_styler import generate_karaoke_subtitles
from clipping.transformation.audio_mixer import compose_clip_audio
from clipping.transformation.video_processor import render_transformed_short
from clipping.publishing.metadata_optimizer import generate_metadata
from clipping.publishing.multi_publisher import publish_to_all_platforms
from clipping.analytics.database import AnalyticsDB

logger = logging.getLogger("clipping.orchestrator")


def download_source_media(video_url: str, temp_prefix: str = "source") -> Tuple[Path, Path]:
    """
    Downloads source audio and video streams using yt-dlp at high quality.
    Returns: (audio_path, video_path)
    """
    from yt_dlp import YoutubeDL

    audio_path = Path(f"{temp_prefix}_audio.wav")
    video_path = Path(f"{temp_prefix}_video.mp4")

    # 1. Download audio stream in high-fidelity WAV (uncompressed for optimal transcription & silence detection)
    audio_opts = {
        "format": "ba/b",
        "outtmpl": f"{temp_prefix}_audio.%(ext)s",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "quiet": True,
        "no_warnings": True,
    }
    with YoutubeDL(audio_opts) as ydl:
        ydl.download([video_url])

    # 2. Download video stream (up to 1080p 60fps)
    video_opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "outtmpl": f"{temp_prefix}_video.%(ext)s",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    with YoutubeDL(video_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        filename = ydl.prepare_filename(info)
        base, _ = os.path.splitext(filename)
        if os.path.exists(base + ".mp4"):
            video_path = Path(base + ".mp4")
        elif os.path.exists(filename):
            video_path = Path(filename)

    return audio_path, video_path


def run_pipeline(
    mode: str = "auto",
    url: Optional[str] = None,
    dry_run: bool = False,
    clips_to_generate: int = CLIPS_PER_DAY,
    privacy: str = "public",
    audio_mode: str = "original",
    voice: str = "andrew",
    profile_name: Optional[str] = None,
) -> List[str]:
    """
    Executes the multi-profile autonomous clipping and publishing pipeline.
    """
    prof: ClipProfile = get_profile(profile_name)

    logger.info("=================================================================")
    logger.info(f"STARTING AUTONOMOUS SHORTS PIPELINE: [{prof.display_name.upper()}]")
    logger.info(f"Profile: {prof.name} | Layout: {prof.layout_mode} | Mode: {mode}")
    logger.info(f"Dry-Run: {dry_run} | Target Clips: {clips_to_generate}")
    logger.info("=================================================================")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    compliance = ComplianceFilter()
    db = AnalyticsDB()
    published_urls: List[str] = []

    target_video: Optional[VideoMeta] = None

    # Step 1: Discovery or URL resolution
    if mode == "url" and url:
        from yt_dlp import YoutubeDL
        with YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            target_video = VideoMeta.from_ytdlp(info)
    else:
        logger.info(f"[1/8] Discovering trending candidate videos for {prof.display_name}...")
        candidates = search_niche_videos(
            max_results_per_kw=10,
            custom_keywords=prof.search_keywords,
        )

        # Prioritize channels on whitelist if matched
        if prof.channel_whitelist:
            whitelist_lower = [c.lower() for c in prof.channel_whitelist]
            prioritized = [v for v in candidates if any(w in v.channel.lower() for w in whitelist_lower)]
            other = [v for v in candidates if not any(w in v.channel.lower() for w in whitelist_lower)]
            candidates = prioritized + other

        ranked = rank_by_velocity(candidates)

        for v in ranked:
            safe, reason = compliance.is_safe(v)
            if safe:
                target_video = v
                break
            else:
                logger.info(f"  [Skipped] {v.title[:40]}... -> {reason}")

    if not target_video:
        logger.warning(f"No compliance-approved source video found for {prof.name}. Pipeline paused.")
        return []

    logger.info(f"-> Selected Source Video: '{target_video.title}' by {target_video.channel}")
    logger.info(f"-> URL: {target_video.url} (Views: {target_video.view_count:,})")

    # Step 2: Multi-Signal Extraction - Heatmap Replay Curve
    logger.info("[2/8] Extracting YouTube 'Most Replayed' heatmap curve...")
    heatmap_points = fetch_heatmap(target_video.url)
    peak_windows = find_peak_windows(
        heatmap_points,
        video_duration_sec=target_video.duration,
        top_n=max(6, clips_to_generate * 2),
    )

    # Step 3: Multi-Signal Extraction - Viewer Comment Timestamps & Hype Mining
    logger.info("[3/8] Mining viewer comments for timestamp mentions & hype spikes...")
    comment_peaks = extract_comment_timestamp_peaks(target_video.url, max_comments=150)

    # Step 4: Download Media & Multi-Signal Audio Peak/Silence Detection
    logger.info("[4/8] Downloading source media in high-fidelity for audio energy analysis...")
    prefix = f"temp_source_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    audio_path, video_path = download_source_media(target_video.url, temp_prefix=prefix)

    try:
        logger.info("Analyzing audio waveform for scream/energy spikes and silence gaps...")
        audio_analysis = analyze_audio_energy(str(audio_path))

        # Step 5: Faster-Whisper GPU Transcription
        logger.info("[5/8] Transcribing dialogue with word-level timestamps...")
        transcript, word_segments = transcribe_audio(str(audio_path))

        # Step 6: Multi-Signal Fusion & Contextual Boundary Expansion
        logger.info(f"[6/8] Selecting top {clips_to_generate} viral segments with complete narrative arcs...")
        selected_clips = select_viral_clips(
            transcript=transcript,
            heatmap_peaks=peak_windows,
            word_segments=word_segments,
            source_meta=target_video,
            top_n=clips_to_generate,
            profile=prof,
            comment_peaks=comment_peaks,
            audio_analysis=audio_analysis,
        )

        if not selected_clips:
            logger.warning("No valid clip candidates identified.")
            return []

        # Step 7: Transformative Rendering & Subtitles
        logger.info(f"[7/8] Rendering {len(selected_clips)} Short(s) using {prof.layout_mode} layout...")

        for idx, clip in enumerate(selected_clips):
            clip_idx = idx + 1
            logger.info(f"\n--- Processing Clip {clip_idx}/{len(selected_clips)} ({clip.duration:.1f}s) ---")

            commentary = ""
            master_audio = None

            if audio_mode == "soothing":
                logger.info(f"Synthesizing soothing narration (voice='{voice}')...")
                commentary = write_commentary(clip)
                tts_path = OUTPUT_DIR / f"tts_narration_{clip_idx}.mp3"
                generate_narration(commentary, tts_path, voice=voice)
                master_audio = OUTPUT_DIR / f"master_audio_{clip_idx}.wav"
                compose_clip_audio(tts_path, master_audio)
                sub_source = commentary
            else:
                logger.info("Preserving authentic streamer dialogue and audio reactions.")
                sub_source = clip.word_segments if clip.word_segments else clip.transcript_segment

            # Word-level ASS karaoke subtitles with profile typography
            sub_path = OUTPUT_DIR / f"karaoke_subs_{clip_idx}.ass"
            generate_karaoke_subtitles(
                word_segments_or_text=sub_source,
                output_path=sub_path,
                total_duration=clip.duration,
                profile=prof,
            )

            # Render 1080x1920 Short (Smart Split-Screen / Action Framing)
            short_path = OUTPUT_DIR / f"short_clip_{clip_idx}.mp4"
            render_transformed_short(
                source_video=video_path,
                clip=clip,
                master_audio=master_audio,
                subtitle_file=sub_path,
                hook_title=clip.hook_sentence,
                output_path=short_path,
                profile=prof,
            )

            # Metadata generation
            metadata = generate_metadata(clip, commentary, profile=prof)
            ab_variant = "A" if clip_idx % 2 != 0 else "B"

            # Step 8: Multi-Platform Publishing
            logger.info(f"[8/8] Syndicating to platforms [Variant {ab_variant}]...")
            pub_results = publish_to_all_platforms(
                video_path=short_path,
                metadata=metadata,
                ab_variant=ab_variant,
                privacy=privacy,
                dry_run=dry_run,
            )

            yt_url = pub_results.get("youtube")

            if yt_url:
                published_urls.append(yt_url)
                vid_id = yt_url.split("/")[-1]
                chosen_title = metadata["title_a"] if ab_variant == "A" else metadata["title_b"]

                db.insert_clip(
                    video_id=vid_id,
                    video_url=yt_url,
                    source_url=target_video.url,
                    source_channel=target_video.channel,
                    title=chosen_title,
                    title_variant=ab_variant,
                    clip_duration=clip.duration,
                    heatmap_score=clip.heatmap_score,
                    commentary_length=len(commentary.split()) if commentary else 0,
                )

        # Mark source video as processed
        compliance.register_processed(target_video.video_id, len(selected_clips))

        # Cloud sync via rclone
        if published_urls and not dry_run:
            logger.info(f"Syncing generated clips to cloud ({GDRIVE_REMOTE})...")
            try:
                subprocess.run(["rclone", "copy", str(OUTPUT_DIR), GDRIVE_REMOTE, "-v"], capture_output=True, text=True)
                logger.info("Clips successfully synced.")
            except Exception as e:
                logger.warning(f"rclone sync warning: {e}")

    finally:
        # Cleanup temporary source media
        logger.info("Cleaning up temporary source media files...")
        for p in [audio_path, video_path]:
            if p and p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass

    logger.info("=================================================================")
    logger.info(f"PIPELINE COMPLETE: {len(published_urls)} Short(s) processed for [{prof.display_name}].")
    logger.info("=================================================================")
    return published_urls
