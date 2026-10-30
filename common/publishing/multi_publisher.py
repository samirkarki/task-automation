#!/usr/bin/env python3
"""
Unified Multi-Platform Video Publisher
Coordinates simultaneous deployment to YouTube Shorts, Instagram Reels, and TikTok.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from common.publishing.youtube_uploader import upload_short_to_youtube
from common.publishing.instagram_uploader import upload_reel_to_instagram
from common.publishing.tiktok_uploader import upload_video_to_tiktok

logger = logging.getLogger("common.publishing.multi")


def publish_to_all_platforms(
    video_path: Path,
    metadata: Dict[str, Any],
    video_public_url: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Optional[str]]:
    """
    Publishes video across YouTube Shorts, Instagram Reels, and TikTok.
    Returns dictionary with upload IDs per platform.
    """
    results: Dict[str, Optional[str]] = {
        "youtube": None,
        "instagram": None,
        "tiktok": None,
    }

    # 1. YouTube Shorts
    try:
        results["youtube"] = upload_short_to_youtube(video_path, metadata, dry_run=dry_run)
    except Exception as e:
        logger.error(f"YouTube publishing failed: {e}")

    # 2. Instagram Reels
    try:
        results["instagram"] = upload_reel_to_instagram(
            video_path, metadata, video_public_url=video_public_url, dry_run=dry_run
        )
    except Exception as e:
        logger.error(f"Instagram publishing failed: {e}")

    # 3. TikTok
    try:
        results["tiktok"] = upload_video_to_tiktok(video_path, metadata, dry_run=dry_run)
    except Exception as e:
        logger.error(f"TikTok publishing failed: {e}")

    return results
