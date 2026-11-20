"""
YouTube Comment & Viewer Activity Miner.
Extracts timestamp mentions, emoji frequencies, and engagement clusters from
viewer comments to pinpoint viral highlights and fan-favorite moments.
"""

from collections import defaultdict
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("clipping.extraction.comment_miner")

# High-impact viral reaction keywords and emojis
VIRAL_KEYWORDS = {
    "💀": 3.0,
    "😭": 2.5,
    "🔥": 2.0,
    "lmao": 2.0,
    "lmfao": 2.5,
    "wtf": 2.5,
    "bruh": 2.0,
    "bro": 1.0,
    "died": 2.0,
    "dead": 2.0,
    "crazy": 1.5,
    "insane": 2.0,
    "glitch": 2.5,
    "wasted": 2.5,
    "clip": 3.0,
    "clip it": 3.5,
    "reaction": 2.0,
    "face": 1.5,
    "scream": 2.5,
    "caught": 1.5,
    "hacker": 2.0,
    "unreal": 2.0,
    "clutch": 3.0,
}

# Regex for MM:SS or HH:MM:SS timestamps
TIMESTAMP_PATTERN = re.compile(r"\b(?:(\d{1,2}):)?([0-5]?\d):([0-5]\d)\b")


def parse_timestamp_str(t_str: str) -> Optional[int]:
    """Converts MM:SS or HH:MM:SS string to integer seconds."""
    try:
        parts = list(map(int, t_str.strip().split(":")))
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return None
    except Exception:
        return None


def score_comment_text(text: str, likes: int = 0) -> Tuple[float, List[str]]:
    """
    Computes a virality weight for a comment based on likes and trigger keywords.
    """
    weight = 1.0 + min(float(likes) / 20.0, 5.0)  # Up to 5.0 bonus for high likes
    matched_triggers = []
    text_lower = text.lower()

    for kw, kw_weight in VIRAL_KEYWORDS.items():
        if kw in text_lower:
            weight += kw_weight
            matched_triggers.append(kw)

    return weight, matched_triggers


def extract_comment_timestamp_peaks(
    video_url: str,
    max_comments: int = 150,
    cluster_window_sec: int = 15,
) -> List[Tuple[float, float, str]]:
    """
    Scrapes video comments using yt-dlp and clusters timestamp mentions.
    Returns: List of (peak_timestamp_sec, cluster_score, top_comment_context)
    """
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        logger.warning("yt-dlp not available for comment mining.")
        return []

    logger.info(f"Mining viewer comments for timestamps from: {video_url}")

    ydl_opts = {
        "getcomments": True,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {"youtube": {"max_comments": [str(max_comments), "all", "0"]}},
    }

    comments_data = []
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            comments_data = info.get("comments") or []
    except Exception as e:
        logger.warning(f"Could not scrape comments (may be disabled or rate-limited): {e}")
        return []

    if not comments_data:
        logger.info("No comments found or comments disabled.")
        return []

    # Map timestamps to list of (score, comment_text)
    timestamp_hits: List[Tuple[int, float, str]] = []

    for c in comments_data:
        text = str(c.get("text", "")).strip()
        if not text:
            continue
        likes = int(c.get("like_count") or 0)
        matches = TIMESTAMP_PATTERN.findall(text)

        if not matches:
            continue

        c_score, triggers = score_comment_text(text, likes)

        for match in matches:
            # Reconstruct timestamp string
            if match[0]:
                ts_str = f"{int(match[0])}:{int(match[1]):02d}:{int(match[2]):02d}"
            else:
                ts_str = f"{int(match[1])}:{int(match[2]):02d}"

            sec = parse_timestamp_str(ts_str)
            if sec is not None and sec > 5:
                timestamp_hits.append((sec, c_score, text[:80]))

    if not timestamp_hits:
        logger.info("No timestamp mentions found in comments.")
        return []

    # Cluster timestamps within cluster_window_sec
    timestamp_hits.sort(key=lambda x: x[0])
    clusters: List[Dict[str, Any]] = []

    for sec, score, text in timestamp_hits:
        added = False
        for cl in clusters:
            if abs(cl["center_sec"] - sec) <= cluster_window_sec:
                cl["count"] += 1
                cl["total_score"] += score
                cl["samples"].append(text)
                # Re-center
                cl["center_sec"] = (cl["center_sec"] + sec) / 2.0
                added = True
                break

        if not added:
            clusters.append({
                "center_sec": float(sec),
                "count": 1,
                "total_score": score,
                "samples": [text],
            })

    # Sort clusters descending by total_score
    clusters.sort(key=lambda x: x["total_score"], reverse=True)

    results: List[Tuple[float, float, str]] = []
    for cl in clusters[:6]:
        best_context = cl["samples"][0] if cl["samples"] else "Viewer highlight"
        results.append((cl["center_sec"], cl["total_score"], best_context))
        logger.info(
            f"  [Comment Peak] t={cl['center_sec']:.1f}s | Score={cl['total_score']:.1f} | "
            f"Mentions={cl['count']} | Context: '{best_context[:40]}...'"
        )

    return results
