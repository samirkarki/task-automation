"""
Viral Clip Selector: Combines Heatmap audience replay peaks, Whisper transcription,
and LLM scoring to isolate high-retention 30-55s candidate segments.
"""

import json
import logging
import re
from typing import List, Tuple, Optional
import requests

from clipping.config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_AUTH_TOKEN, OLLAMA_TIMEOUT, NICHE_CONFIG
from clipping.models import ClipCandidate, VideoMeta, WordSegment

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


def format_peak_segments(transcript: str, peaks: List[Tuple[float, float, float]]) -> str:
    """Extracts transcript lines that fall within peak engagement windows."""
    lines = transcript.splitlines()
    peak_lines = []
    for line in lines:
        if not line.startswith("["):
            continue
        tag = line[1:].split("]")[0]
        sec = time_to_sec(tag)
        for p_start, p_end, p_score in peaks:
            if (p_start - 10) <= sec <= (p_end + 10):
                peak_lines.append(f"{line} (Peak Engagement: {p_score:.2f})")
                break
    return "\n".join(peak_lines[:40]) if peak_lines else transcript[:1200]


def select_viral_clips(
    transcript: str,
    heatmap_peaks: List[Tuple[float, float, float]],
    word_segments: List[WordSegment],
    source_meta: VideoMeta,
    top_n: int = 3,
) -> List[ClipCandidate]:
    """
    Selects top candidate clips. Prioritizes Heatmap peaks, then queries LLM for
    standalone narrative hook and emotional climax.
    """
    peak_text = format_peak_segments(transcript, heatmap_peaks)

    prompt = f"""You are an elite short-form video producer for YouTube Shorts specializing in {NICHE_CONFIG['name']}.
Analyze these transcript highlights from "{source_meta.title}".
Select the top {top_n} viral, standalone clip moments (30 to 55 seconds each).

STRICT SELECTION CRITERIA:
1. DURATION: Each clip MUST be between 30 and 55 seconds (end - start >= 30s).
2. COMPLETE ARC: Must have a strong curiosity-inducing opening hook and a clear payoff.
3. STANDALONE VALUE: Must make complete sense to a viewer who hasn't seen the rest of the video.

Return ONLY a valid JSON array of objects:
[
  {{
    "start": "02:15",
    "end": "02:55",
    "hook_sentence": "The surprising mistake 99% of new entrepreneurs make",
    "commentary_angle": "Analyze why capital allocation matters more than hustle",
    "viral_score": 9.2
  }}
]

Transcript:
{peak_text}"""

    clips_data = []
    try:
        headers = {}
        if OLLAMA_AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {OLLAMA_AUTH_TOKEN}"

        logger.info(f"Querying Ollama ({OLLAMA_MODEL}) for clip selection...")
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
            headers=headers,
            timeout=OLLAMA_TIMEOUT,
        )
        if resp.status_code == 200:
            raw_text = resp.json().get("response", "").strip()
            try:
                clips_data = json.loads(raw_text)
            except Exception:
                match = re.search(r"\[\s*\{.*\}\s*\]", raw_text, re.DOTALL)
                if match:
                    clips_data = json.loads(match.group(0))

            if isinstance(clips_data, dict):
                for k in ["clips", "segments", "data", "items"]:
                    if k in clips_data and isinstance(clips_data[k], list):
                        clips_data = clips_data[k]
                        break
    except Exception as e:
        logger.warning(f"Ollama query failed for clip selection ({e}). Utilizing heatmap peak fallback.")

    # Fallback to heatmap peaks if LLM did not return valid clips
    if not isinstance(clips_data, list) or len(clips_data) == 0:
        logger.info("Using heatmap peaks directly for clip candidates.")
        clips_data = []
        for idx, (p_start, p_end, p_score) in enumerate(heatmap_peaks[:top_n]):
            dur = p_end - p_start
            if dur < 30:
                p_end = p_start + 45
            clips_data.append({
                "start": int(p_start),
                "end": int(p_end),
                "hook_sentence": f"Crucial wisdom on {source_meta.title[:30]}",
                "commentary_angle": "Educational breakdown of the speaker's key strategy",
                "viral_score": round(p_score * 10, 1),
            })

    candidate_clips: List[ClipCandidate] = []
    for item in clips_data:
        if not isinstance(item, dict):
            continue
        start_sec = time_to_sec(item.get("start", 0))
        end_sec = time_to_sec(item.get("end", start_sec + 45))
        duration = end_sec - start_sec

        if duration < 30:
            end_sec = start_sec + 45
            duration = 45
        elif duration > 58:
            end_sec = start_sec + 55
            duration = 55

        # Extract relevant word tokens for subtitles
        clip_words = [w for w in word_segments if start_sec <= w.start <= end_sec]

        # Extract transcript segment
        clip_transcript = " ".join([w.word for w in clip_words]) if clip_words else item.get("hook_sentence", "")

        candidate_clips.append(
            ClipCandidate(
                source_url=source_meta.url,
                source_channel=source_meta.channel,
                source_title=source_meta.title,
                start_sec=float(start_sec),
                end_sec=float(end_sec),
                duration=float(duration),
                heatmap_score=float(item.get("viral_score", 8.0)) / 10.0,
                hook_sentence=item.get("hook_sentence", "Essential Business Insight"),
                commentary_angle=item.get("commentary_angle", "Educational breakdown"),
                transcript_segment=clip_transcript,
                word_segments=clip_words,
            )
        )

    logger.info(f"Generated {len(candidate_clips)} qualified ClipCandidate object(s).")
    return candidate_clips[:top_n]
