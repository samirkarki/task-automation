"""
Master Orchestrator for the Autonomous Multi-Profile YouTube Shorts Pipeline.
Coordinates Discovery -> Lightweight Signal Extraction (Heatmap + Comments) ->
Targeted Section Slicing (Audio & Video) -> Sub-Second Faster-Whisper Transcription ->
Contextual Boundary Expansion -> Smart Split-Screen / Action Framing -> Publishing.
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
from clipping.models import VideoMeta, ClipCandidate, WordSegment
from clipping.profiles import get_profile, DEFAULT_PROFILE
from clipping.profiles.base import ClipProfile
from clipping.discovery.searcher import search_niche_videos
from clipping.discovery.velocity_ranker import rank_by_velocity
from clipping.discovery.compliance_filter import ComplianceFilter
from clipping.extraction.heatmap import fetch_heatmap, find_peak_windows
from clipping.extraction.comment_miner import extract_comment_timestamp_peaks
from clipping.extraction.audio_peak_detector import analyze_audio_energy
from clipping.extraction.transcriber import transcribe_audio
from clipping.extraction.clip_selector import (
    fuse_moment_seeds,
    expand_clip_boundaries_contextually,
)
from clipping.transformation.commentary_writer import write_commentary
from clipping.transformation.tts_narrator import generate_narration
from clipping.transformation.subtitle_styler import generate_karaoke_subtitles
from clipping.transformation.audio_mixer import compose_clip_audio
from clipping.transformation.video_processor import render_transformed_short
from clipping.publishing.metadata_optimizer import generate_metadata
from clipping.publishing.multi_publisher import publish_to_all_platforms
from clipping.analytics.database import AnalyticsDB

logger = logging.getLogger("clipping.orchestrator")


def download_audio_section(
    video_url: str,
    start_sec: float,
    end_sec: float,
    target_path: Path,
) -> Path:
    """
    Downloads ONLY a target audio section (e.g. 60-90s) using yt-dlp.
    Reduces network data by 99%+ compared to downloading full multi-hour streams.
    """
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import download_range_func

    target_path.parent.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(target_path.parent / f"{target_path.stem}_raw.%(ext)s")

    opts = {
        "format": "ba/b",
        "outtmpl": out_tmpl,
        "download_ranges": download_range_func(None, [(int(max(0, start_sec)), int(end_sec))]),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "quiet": True,
        "no_warnings": True,
    }
    logger.info(f"Downloading targeted audio section [{start_sec:.0f}s - {end_sec:.0f}s]...")
    with YoutubeDL(opts) as ydl:
        ydl.download([video_url])

    candidate = target_path.parent / f"{target_path.stem}_raw.wav"
    if candidate.exists():
        if target_path.exists():
            target_path.unlink()
        candidate.rename(target_path)
        return target_path
    if target_path.exists():
        return target_path

    matches = list(target_path.parent.glob(f"{target_path.stem}_raw.*"))
    if matches:
        matches[0].rename(target_path)
        return target_path
    raise RuntimeError(f"Failed to download audio section [{start_sec}-{end_sec}]")


def download_video_section(
    video_url: str,
    start_sec: float,
    end_sec: float,
    target_path: Path,
) -> Path:
    """
    Downloads ONLY the finalized 1080p video clip section (e.g. 35-50s) using yt-dlp.
    """
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import download_range_func

    target_path.parent.mkdir(parents=True, exist_ok=True)
    out_tmpl = str(target_path.parent / f"{target_path.stem}_raw.%(ext)s")

    opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "outtmpl": out_tmpl,
        "download_ranges": download_range_func(None, [(int(max(0, start_sec)), int(end_sec))]),
        "merge_output_format": "mp4",
        "force_keyframes_at_cuts": True,
        "quiet": True,
        "no_warnings": True,
    }
    logger.info(f"Downloading finalized 1080p video section [{start_sec:.0f}s - {end_sec:.0f}s]...")
    with YoutubeDL(opts) as ydl:
        ydl.download([video_url])

    candidate = target_path.parent / f"{target_path.stem}_raw.mp4"
    if candidate.exists():
        if target_path.exists():
            target_path.unlink()
        candidate.rename(target_path)
        return target_path
    if target_path.exists():
        return target_path

    matches = list(target_path.parent.glob(f"{target_path.stem}_raw.*"))
    if matches:
        matches[0].rename(target_path)
        return target_path
    raise RuntimeError(f"Failed to download video section [{start_sec}-{end_sec}]")


def run_pipeline(
    mode: str = "auto",
    url: Optional[str] = None,
    dry_run: bool = False,
    clips_to_generate: int = CLIPS_PER_DAY,
    privacy: str = "public",
    audio_mode: str = "original",
    voice: str = "andrew",
    profile_name: Optional[str] = None,
    output_format_override: Optional[str] = None,
) -> List[str]:
    """
    Executes the multi-profile autonomous clipping and publishing pipeline
    using targeted section slicing (no full-video 9GB downloads).
    """
    prof: ClipProfile = get_profile(profile_name)

    # Allow CLI to override profile output format
    if output_format_override:
        import dataclasses
        prof = dataclasses.replace(prof, output_format=output_format_override)

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
    logger.info(f"-> URL: {target_video.url} (Views: {target_video.view_count:,}, Duration: {target_video.duration/60:.1f}m)")

    # Step 2: Multi-Signal Extraction - Heatmap Replay Curve (Zero Download)
    logger.info("[2/8] Extracting YouTube 'Most Replayed' heatmap curve (instant)...")
    heatmap_points = fetch_heatmap(target_video.url)
    peak_windows = find_peak_windows(
        heatmap_points,
        video_duration_sec=target_video.duration,
        top_n=max(6, clips_to_generate * 2),
    )

    # Step 3: Multi-Signal Extraction - Viewer Comment Timestamps & Hype Mining (Zero Download)
    logger.info("[3/8] Mining viewer comments for timestamp mentions & hype spikes (instant)...")
    comment_peaks = extract_comment_timestamp_peaks(target_video.url, max_comments=150)

    # Step 4: Multi-Signal Fusion into Ranked Candidate Moment Seeds
    logger.info("[4/8] Fusing signals into ranked candidate moment seeds...")
    seeds = fuse_moment_seeds(
        heatmap_peaks=peak_windows,
        comment_peaks=comment_peaks,
        audio_peaks=[],  # Waveform audio peaks will be evaluated on the sliced candidate windows
        video_duration_sec=target_video.duration,
    )

    # Filter out seeds that overlap with intervals already clipped from this video
    unclipped_seeds = []
    for s in seeds:
        t_seed = float(s["timestamp"])
        if db.is_interval_clipped(target_video.url, start_sec=max(0, t_seed - 20), end_sec=t_seed + 40):
            logger.info(f"  [Skipping already-clipped segment] t={t_seed:.1f}s")
            continue
        unclipped_seeds.append(s)

    if not unclipped_seeds:
        logger.warning("All identified viral moments for this video have already been clipped. Trying next run.")
        return []

    # Step 5: Process Top N Candidate Moments with Targeted Section Slicing
    logger.info(f"[5/8] Processing top {clips_to_generate} unclipped moment(s) with targeted section slicing...")
    processed_count = 0

    # Long-form tracking — raw 16:9 clips and their scores
    rendered_short_paths: List[Path] = []
    rendered_short_raw_paths: List[Path] = []
    rendered_clip_scores: List[float] = []
    subtitle_paths: List[Path] = []

    for seed_idx, seed in enumerate(unclipped_seeds):
        if processed_count >= clips_to_generate:
            break

        t_seed = float(seed["timestamp"])
        clip_num = processed_count + 1
        prefix = f"slice_{target_video.video_id}_{seed_idx}_{int(t_seed)}"
        logger.info(f"\n--- Slicing Moment {clip_num}/{clips_to_generate} (seed t={t_seed:.1f}s | Score: {seed['score']:.1f}) ---")

        # Exploratory window for audio: 16s before seed, 48s after seed
        slice_start = max(0.0, t_seed - 16.0)
        slice_end = min(target_video.duration, t_seed + 48.0)
        audio_slice_path = OUTPUT_DIR / f"{prefix}_audio.wav"

        try:
            # Download ONLY the ~64s audio slice (~1.5 MB)
            download_audio_section(target_video.url, slice_start, slice_end, audio_slice_path)

            # Analyze audio energy (screams & silence gaps)
            audio_analysis = analyze_audio_energy(str(audio_slice_path))
            silences = audio_analysis.get("silences", [])

            # Transcribe ONLY this 64s audio slice with Faster-Whisper (takes ~1.5 seconds!)
            transcript_text, word_segments = transcribe_audio(
                str(audio_slice_path),
                offset_seconds=slice_start,
            )

            # Contextual boundary expansion (snaps to sentence start and silence)
            c_start, c_end = expand_clip_boundaries_contextually(
                seed_timestamp=t_seed,
                word_segments=word_segments,
                silences=[(s + slice_start, e + slice_start) for s, e in silences],
                video_duration=target_video.duration,
                min_duration=prof.min_clip_duration,
                max_duration=prof.max_clip_duration,
                optimal_duration=prof.optimal_clip_duration,
            )

            clip_words = [w for w in word_segments if c_start <= w.start <= c_end]
            clip_transcript = " ".join([w.word for w in clip_words]) if clip_words else seed.get("context", "")

            # Set hook title
            seed_context = seed.get("context", "")
            if "💀" in seed_context or "lmao" in seed_context.lower() or "bro" in seed_context.lower():
                hook_sentence = seed_context[:45]
            elif prof.name == "game-gta6":
                hook_sentence = "GTA 6 INSANE MOMENT 💀"
            elif prof.name == "mrbeast":
                hook_sentence = "HE ACTUALLY PULLED THIS OFF 😱"
            else:
                hook_sentence = f"{target_video.title[:35]}"

            clip = ClipCandidate(
                source_url=target_video.url,
                source_channel=target_video.channel,
                source_title=target_video.title,
                start_sec=c_start,
                end_sec=c_end,
                duration=round(c_end - c_start, 2),
                heatmap_score=min(float(seed["score"]) / 10.0, 1.0),
                hook_sentence=hook_sentence,
                commentary_angle=f"Stream highlight from {target_video.channel}",
                transcript_segment=clip_transcript,
                word_segments=clip_words,
                is_pre_cut=True,
            )

            # Step 6: Download ONLY the finalized 1080p video clip section (~15 MB)
            video_slice_path = OUTPUT_DIR / f"{prefix}_video.mp4"
            download_video_section(target_video.url, c_start, c_end, video_slice_path)

            # Step 7: Subtitles & Transformative Rendering
            logger.info(f"[6/8] Rendering Short #{clip_num} [{prof.layout_mode}] ({clip.duration:.1f}s)...")
            sub_path = OUTPUT_DIR / f"karaoke_subs_{clip_num}.ass"
            generate_karaoke_subtitles(
                word_segments_or_text=clip.word_segments if clip.word_segments else clip.transcript_segment,
                output_path=sub_path,
                total_duration=clip.duration,
                profile=prof,
                start_offset=clip.start_sec,
            )

            short_path = OUTPUT_DIR / f"short_clip_{clip_num}.mp4"
            render_transformed_short(
                source_video=video_slice_path,
                clip=clip,
                master_audio=None,
                subtitle_file=sub_path,
                hook_title=clip.hook_sentence,
                output_path=short_path,
                profile=prof,
            )

            # Step 8: Metadata & Multi-Platform Publishing
            metadata = generate_metadata(clip, "", profile=prof)
            ab_variant = "A" if clip_num % 2 != 0 else "B"

            logger.info(f"[7/8] Syndicating to platforms [Variant {ab_variant}]...")
            pub_results = publish_to_all_platforms(
                video_path=short_path,
                metadata=metadata,
                ab_variant=ab_variant,
                privacy=privacy,
                dry_run=dry_run,
            )

            yt_url = pub_results.get("youtube")
            vid_id = yt_url.split("/")[-1] if yt_url else f"local_{int(t_seed)}"
            chosen_title = metadata["title_a"] if ab_variant == "A" else metadata["title_b"]

            if yt_url:
                published_urls.append(yt_url)

            # Track for long-form compilation
            rendered_short_paths.append(short_path)
            rendered_short_raw_paths.append(video_slice_path)
            rendered_clip_scores.append(clip.heatmap_score)
            subtitle_paths.append(sub_path)

            # Record in SQLite database with interval tracking
            db.insert_clip(
                video_id=vid_id,
                video_url=yt_url or f"https://youtube.com/shorts/{vid_id}",
                source_url=target_video.url,
                source_channel=target_video.channel,
                title=chosen_title,
                title_variant=ab_variant,
                clip_duration=clip.duration,
                start_sec=clip.start_sec,
                end_sec=clip.end_sec,
                heatmap_score=clip.heatmap_score,
                commentary_length=0,
            )
            processed_count += 1

        except Exception as e:
            logger.error(f"Error processing clip seed at {t_seed:.1f}s: {e}", exc_info=True)
        finally:
            # Clean up audio slice always; keep raw video slice if long-form enabled
            output_format = getattr(prof, "output_format", "shorts")
            keep_video_slice = output_format in ("longform", "both")
            files_to_clean = [audio_slice_path]
            if not keep_video_slice:
                files_to_clean.append(OUTPUT_DIR / f"{prefix}_video.mp4")
            for p in files_to_clean:
                if p and p.exists():
                    try:
                        p.unlink()
                    except OSError:
                        pass

    # --- Long-Form Compilation (if profile output_format in "longform" | "both") ---
    output_format = getattr(prof, "output_format", "shorts")
    if output_format in ("longform", "both") and len(rendered_short_raw_paths) >= 2:
        logger.info(
            f"[Long-Form] Assembling {len(rendered_short_raw_paths)}-clip compilation "
            f"(target: {getattr(prof, 'longform_duration', 600.0):.0f}s)..."
        )
        try:
            from clipping.transformation.bumper_renderer import render_bumper
            from clipping.transformation.longform_renderer import render_longform_compilation

            brand_name = getattr(prof, "channel_brand_name", "ClipBot")
            avatar_path = getattr(prof, "attribution_avatar_path", None)

            intro_path = OUTPUT_DIR / "bumper_intro.mp4"
            outro_path = OUTPUT_DIR / "bumper_outro.mp4"

            render_bumper(
                channel_brand_name=brand_name,
                game_title=prof.display_name,
                output_path=intro_path,
                avatar_path=avatar_path,
                episode_label=f"Best Moments \u2014 {datetime.now().strftime('%b %Y')}",
            )
            render_bumper(
                channel_brand_name=brand_name,
                game_title=prof.display_name,
                output_path=outro_path,
                avatar_path=avatar_path,
                episode_label="Like & Subscribe for more!",
            )

            longform_path = OUTPUT_DIR / "compilation_longform.mp4"
            result = render_longform_compilation(
                clip_paths=rendered_short_raw_paths,
                clip_scores=rendered_clip_scores,
                output_path=longform_path,
                intro_bumper_path=intro_path if intro_path.exists() else None,
                outro_bumper_path=outro_path if outro_path.exists() else None,
                target_duration=getattr(prof, "longform_duration", 600.0),
                channel_brand_name=brand_name,
                game_title=prof.display_name,
                accent_color="0x00FFFF" if prof.name == "game-gta6" else "0xFFFF00",
                mute_game_music=getattr(prof, "mute_game_music", True),
            )

            if result and result.exists():
                logger.info(f"Long-form compilation ready: {result}")
                if not dry_run:
                    longform_meta = generate_metadata(
                        ClipCandidate(
                            source_url=target_video.url,
                            source_channel=target_video.channel,
                            source_title=f"{prof.display_name} Best Moments Compilation",
                            start_sec=0.0,
                            end_sec=getattr(prof, "longform_duration", 600.0),
                            duration=getattr(prof, "longform_duration", 600.0),
                            heatmap_score=0.9,
                            hook_sentence=f"{prof.display_name} Best Moments \U0001f525",
                            commentary_angle="Best moments compilation",
                            transcript_segment="",
                            word_segments=[],
                            is_pre_cut=True,
                        ),
                        "",
                        profile=prof,
                    )
                    publish_to_all_platforms(
                        video_path=result,
                        metadata=longform_meta,
                        ab_variant="A",
                        privacy=privacy,
                        dry_run=dry_run,
                    )

            # Clean up raw video slices now that long-form is assembled
            for raw_p in rendered_short_raw_paths:
                if raw_p and raw_p.exists():
                    try:
                        raw_p.unlink()
                    except OSError:
                        pass

        except Exception as lf_err:
            logger.error(f"Long-form compilation failed: {lf_err}", exc_info=True)

    # Mark video in compliance filter with count of generated clips
    compliance.register_processed(target_video.video_id, processed_count)

    # Cloud sync via rclone if configured
    if published_urls and not dry_run:
        logger.info(f"Syncing generated clips to cloud ({GDRIVE_REMOTE})...")
        try:
            subprocess.run(["rclone", "copy", str(OUTPUT_DIR), GDRIVE_REMOTE, "-v"], capture_output=True, text=True)
            logger.info("Clips successfully synced.")
        except Exception as e:
            logger.warning(f"rclone sync warning: {e}")

    logger.info("=================================================================")
    logger.info(f"PIPELINE COMPLETE: {processed_count} Short(s) generated for [{prof.display_name}].")
    logger.info("=================================================================")
    return published_urls
