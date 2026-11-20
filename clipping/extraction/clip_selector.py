"""
Context-Aware Multi-Signal Viral Clip Selector.
Fuses YouTube Heatmap replay spikes, Comment timestamp clusters, and Audio scream/energy spikes
to identify peak viral moments, expanding boundaries naturally to sentence and silence limits
to preserve complete narrative context (Setup -> Climax -> Payoff).
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import requests

from clipping.config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_AUTH_TOKEN, OLLAMA_TIMEOUT
from clipping.models import ClipCandidate, VideoMeta, WordSegment
from clipping.profiles.base import ClipProfile
from clipping.profiles import DEFAULT_PROFILE
from clipping.extraction.audio_peak_detector import find_clean_silence_boundary

logger = logging.getLogger("clipping.extraction.clip_selector")


def time_to_sec(t_str) -> int:
    """Converts MM:SS, HH:MM:SS, int, or float timestamp string to seconds."""
    try:
        if isinstance(t_str, (int, float)):
            return int(t_str)
        t_clean = str(t_str).strip().strip('"').strip("'")
        parts = list(map(int, t_clean.split(":")))
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return int(float(t_clean))
    except Exception:
        return 0


def fuse_moment_seeds(
    heatmap_peaks: List[Tuple[float, float, float]],
    comment_peaks: List[Tuple[float, float, str]],
    audio_peaks: List[Tuple[float, float, float]],
    video_duration_sec: float,
    merge_window_sec: float = 12.0,
) -> List[Dict[str, Any]]:
    """
    Fuses multiple signals into ranked candidate moment seeds:
      - Heatmap "Most Replayed" peaks (weight: 1.0)
      - Viewer Comment timestamps & hype emojis (weight: 1.3)
      - Audio scream/loudness spikes (weight: 1.1)
    """
    raw_seeds: List[Dict[str, Any]] = []

    # 1. Ingest comment peaks
    for c_time, c_score, c_text in comment_peaks:
        raw_seeds.append({
            "timestamp": c_time,
            "score": c_score * 1.3,
            "source": "comments",
            "context": c_text,
        })

    # 2. Ingest heatmap peaks
    for h_start, h_end, h_score in heatmap_peaks:
        center = (h_start + h_end) / 2.0
        raw_seeds.append({
            "timestamp": center,
            "score": h_score * 10.0,
            "source": "heatmap",
            "context": "Audience Replay Peak",
        })

    # 3. Ingest audio scream/energy spikes
    for a_time, a_db, a_intensity in audio_peaks:
        raw_seeds.append({
            "timestamp": a_time,
            "score": min(a_intensity * 2.0, 8.0) * 1.1,
            "source": "audio_scream",
            "context": f"High energy volume spike ({a_db:.1f}dB)",
        })

    if not raw_seeds:
        # Fallback to standard milestone intervals if no signals detected
        logger.info("No external signals detected; generating strategic milestone seeds.")
        percentages = [0.18, 0.38, 0.58, 0.75, 0.88]
        for pct in percentages:
            t = video_duration_sec * pct
            if 30 <= t <= (video_duration_sec - 40):
                raw_seeds.append({
                    "timestamp": t,
                    "score": 5.0,
                    "source": "milestone",
                    "context": "Stream milestone highlight",
                })

    # Cluster seeds that refer to the same moment (within merge_window_sec)
    raw_seeds.sort(key=lambda x: x["timestamp"])
    merged_seeds: List[Dict[str, Any]] = []

    for s in raw_seeds:
        matched = False
        for m in merged_seeds:
            if abs(m["timestamp"] - s["timestamp"]) <= merge_window_sec:
                m["score"] += s["score"]
                m["sources"].append(s["source"])
                if s["source"] == "comments" and s.get("context"):
                    m["context"] = s["context"]
                matched = True
                break

        if not matched:
            merged_seeds.append({
                "timestamp": s["timestamp"],
                "score": s["score"],
                "sources": [s["source"]],
                "context": s.get("context", "Viral Highlight"),
            })

    # Sort descending by composite score
    merged_seeds.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"Fused {len(merged_seeds)} candidate moment seed(s) across all signals.")
    return merged_seeds


def expand_clip_boundaries_contextually(
    seed_timestamp: float,
    word_segments: List[WordSegment],
    silences: List[Tuple[float, float]],
    video_duration: float,
    min_duration: float = 18.0,
    max_duration: float = 58.0,
    optimal_duration: float = 38.0,
) -> Tuple[float, float]:
    """
    Context-Aware Boundary Expansion:
    1. Looks back ~8-18s from the peak seed to locate the start of the thought/sentence in word_segments.
    2. Snaps start to the nearest preceding silence gap (>0.25s).
    3. Looks forward ~12-25s past the peak to let the reaction/laughter complete.
    4. Snaps end to the nearest trailing silence gap.
    5. Naturally respects min_duration and max_duration without arbitrary clamping.
    """
    # Target window around seed
    rough_lead_in = 12.0
    rough_lead_out = optimal_duration - rough_lead_in

    ideal_start = max(0.0, seed_timestamp - rough_lead_in)
    ideal_end = min(video_duration, seed_timestamp + rough_lead_out)

    # 1. Align start to nearest sentence start in word_segments
    if word_segments:
        # Find words within [ideal_start - 6s, ideal_start + 4s]
        candidate_words = [
            w for w in word_segments
            if (ideal_start - 6.0) <= w.start <= (ideal_start + 4.0)
        ]
        # Look for a capitalized word or word following punctuation
        for w in candidate_words:
            if w.word and (w.word[0].isupper() or w.word.startswith((".", "!", "?"))):
                ideal_start = max(0.0, w.start - 0.2)
                break

    # 2. Snap start to preceding silence boundary
    clean_start = find_clean_silence_boundary(ideal_start, silences, direction="before", max_search_sec=4.0)
    clean_start = max(0.0, clean_start)

    # 3. Align end to sentence completion or silence
    if word_segments:
        candidate_end_words = [
            w for w in word_segments
            if (clean_start + min_duration) <= w.end <= (clean_start + max_duration)
        ]
        # Look for sentence-terminating punctuation (. ! ?)
        punct_ends = [
            w.end for w in candidate_end_words
            if any(p in w.word for p in [".", "!", "?", "...", "💀"])
        ]
        if punct_ends:
            # Pick the punctuation closest to optimal_duration from start
            target_t = clean_start + optimal_duration
            best_p = min(punct_ends, key=lambda t: abs(t - target_t))
            ideal_end = best_p + 0.4
        else:
            ideal_end = clean_start + optimal_duration

    # 4. Snap end to trailing silence boundary
    clean_end = find_clean_silence_boundary(ideal_end, silences, direction="after", max_search_sec=4.0)
    clean_end = min(video_duration, clean_end)

    # 5. Final duration verification
    actual_dur = clean_end - clean_start
    if actual_dur < min_duration:
        clean_end = min(video_duration, clean_start + min_duration + 2.0)
    elif actual_dur > max_duration:
        clean_end = clean_start + max_duration

    clean_start = round(clean_start, 2)
    clean_end = round(clean_end, 2)

    logger.debug(
        f"Context expansion around seed t={seed_timestamp:.1f}s -> "
        f"[{clean_start}s to {clean_end}s] (dur={clean_end - clean_start:.1f}s)"
    )
    return clean_start, clean_end


def select_viral_clips(
    transcript: str,
    heatmap_peaks: List[Tuple[float, float, float]],
    word_segments: List[WordSegment],
    source_meta: VideoMeta,
    top_n: int = 3,
    profile: Optional[ClipProfile] = None,
    comment_peaks: Optional[List[Tuple[float, float, str]]] = None,
    audio_analysis: Optional[Dict[str, Any]] = None,
) -> List[ClipCandidate]:
    """
    Selects top candidate clips using multi-signal fusion (heatmap + comments + audio)
    and context-aware boundary expansion.
    """
    prof = profile or DEFAULT_PROFILE
    c_peaks = comment_peaks or []
    a_peaks = audio_analysis.get("peaks", []) if audio_analysis else []
    silences = audio_analysis.get("silences", []) if audio_analysis else []

    # Step 1: Fuse all signals into ranked moment seeds
    seeds = fuse_moment_seeds(
        heatmap_peaks=heatmap_peaks,
        comment_peaks=c_peaks,
        audio_peaks=a_peaks,
        video_duration_sec=source_meta.duration,
    )

    candidate_clips: List[ClipCandidate] = []
    selected_ranges: List[Tuple[float, float]] = []

    # Step 2: Contextual boundary expansion for each top seed
    for seed in seeds:
        t_seed = float(seed["timestamp"])
        c_start, c_end = expand_clip_boundaries_contextually(
            seed_timestamp=t_seed,
            word_segments=word_segments,
            silences=silences,
            video_duration=source_meta.duration,
            min_duration=prof.min_clip_duration,
            max_duration=prof.max_clip_duration,
            optimal_duration=prof.optimal_clip_duration,
        )

        # Check overlap with already chosen clips (avoid duplicate coverage)
        overlap = False
        for s_start, s_end in selected_ranges:
            if not (c_end <= s_start or c_start >= s_end):
                overlap = True
                break

        if overlap:
            continue

        selected_ranges.append((c_start, c_end))

        # Words in this segment
        clip_words = [w for w in word_segments if c_start <= w.start <= c_end]
        clip_transcript = " ".join([w.word for w in clip_words]) if clip_words else seed.get("context", "")

        # Default hook title from context
        seed_context = seed.get("context", "")
        if "💀" in seed_context or "lmao" in seed_context.lower() or "bro" in seed_context.lower():
            default_hook = seed_context[:45]
        elif prof.name == "game-gta6":
            default_hook = f"GTA 6 INSANE MOMENT 💀"
        elif prof.name == "mrbeast":
            default_hook = f"HE ACTUALLY PULLED THIS OFF 😱"
        else:
            default_hook = f"{source_meta.title[:35]}"

        candidate_clips.append(
            ClipCandidate(
                source_url=source_meta.url,
                source_channel=source_meta.channel,
                source_title=source_meta.title,
                start_sec=c_start,
                end_sec=c_end,
                duration=round(c_end - c_start, 2),
                heatmap_score=min(float(seed["score"]) / 10.0, 1.0),
                hook_sentence=default_hook,
                commentary_angle=f"Stream highlight from {source_meta.channel}",
                transcript_segment=clip_transcript,
                word_segments=clip_words,
            )
        )

        if len(candidate_clips) >= top_n:
            break

    # Step 3: LLM Refinement for punchy Short hook titles if Ollama is accessible
    if candidate_clips:
        try:
            logger.info(f"Querying Ollama ({OLLAMA_MODEL}) to generate elite viral hook titles...")
            headers = {}
            if OLLAMA_AUTH_TOKEN:
                headers["Authorization"] = f"Bearer {OLLAMA_AUTH_TOKEN}"

            prompt_items = []
            for i, c in enumerate(candidate_clips):
                prompt_items.append(
                    f"Clip {i+1} ({c.start_sec:.0f}s-{c.end_sec:.0f}s):\n"
                    f"Context: {c.hook_sentence}\n"
                    f"Transcript snippet: {c.transcript_segment[:160]}\n"
                )

            llm_prompt = f"""You are a master YouTube Shorts editor for {prof.display_name}.
Review these {len(candidate_clips)} extracted clip moments from "{source_meta.title}".
Generate a viral, curiosity-inducing hook title (under 7 words, all caps, optional single emoji) for each clip.

Clips:
{"".join(prompt_items)}

Return ONLY a JSON array of strings, e.g.:
["BRO COULD NOT BELIEVE THIS 💀", "THE POLICE REACTION WAS INSANE 😭"]"""

            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": llm_prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.3},
                },
                headers=headers,
                timeout=min(OLLAMA_TIMEOUT, 60),
            )

            if resp.status_code == 200:
                raw_json = resp.json().get("response", "").strip()
                parsed = json.loads(raw_json)
                if isinstance(parsed, list):
                    for idx, title_str in enumerate(parsed[:len(candidate_clips)]):
                        if isinstance(title_str, str) and len(title_str.strip()) > 3:
                            candidate_clips[idx].hook_sentence = title_str.strip()
        except Exception as e:
            logger.debug(f"LLM hook title refinement skipped ({e}); using context-derived hook titles.")

    logger.info(f"Finalized {len(candidate_clips)} contextually expanded clip(s).")
    return candidate_clips
