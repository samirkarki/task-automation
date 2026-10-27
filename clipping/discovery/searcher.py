"""
Search engine for finding high-performing long-form videos using yt-dlp.
Uses zero YouTube API quota.
"""

import logging
from typing import List, Dict, Any, Optional
from clipping.config import NICHE_CONFIG
from clipping.models import VideoMeta

logger = logging.getLogger("clipping.discovery.searcher")


def search_niche_videos(max_results_per_kw: int = 15, custom_keywords: Optional[List[str]] = None) -> List[VideoMeta]:
    """
    Searches YouTube for trending long-form content in the target niche.
    Uses yt-dlp search (costs zero API quota).
    """
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        logger.error("yt_dlp is not installed. Please install via: pip install yt-dlp")
        return []

    keywords = custom_keywords or NICHE_CONFIG.get("search_keywords", ["business advice podcast"])
    all_results: List[VideoMeta] = []
    seen_ids = set()

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        for kw in keywords:
            search_query = f"ytsearch{max_results_per_kw}:{kw}"
            logger.info(f"Querying YouTube via yt-dlp: '{kw}'...")
            try:
                info = ydl.extract_info(search_query, download=False)
                entries = info.get("entries") or []
                for entry in entries:
                    if not entry:
                        continue
                    vid_id = entry.get("id")
                    if not vid_id or vid_id in seen_ids:
                        continue

                    # Filter for long-form candidates (duration > 600s = 10 min)
                    duration = float(entry.get("duration") or 0.0)
                    if duration < 600:
                        continue

                    seen_ids.add(vid_id)
                    meta = VideoMeta.from_ytdlp(entry)
                    all_results.append(meta)
            except Exception as e:
                logger.warning(f"Error querying yt-dlp for '{kw}': {e}")

    logger.info(f"Discovered {len(all_results)} candidate long-form videos.")
    return all_results
