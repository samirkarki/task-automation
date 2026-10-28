"""
Multi-Platform Publishing Orchestrator.
Simultaneously publishes transformed 9:16 vertical clips across YouTube Shorts,
Instagram Reels, and TikTok via their respective direct APIs.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from clipping.publishing.youtube_uploader import upload_short_to_youtube
from clipping.publishing.instagram_uploader import upload_reel_to_instagram
from clipping.publishing.tiktok_uploader import upload_video_to_tiktok

logger = logging.getLogger("clipping.publishing.multi_publisher")


def publish_to_all_platforms(
    video_path: Path,
    metadata: Dict[str, Any],
    ab_variant: str = "A",
    privacy: str = "public",
    dry_run: bool = False,
) -> Dict[str, Optional[str]]:
    """
    Syndicates the rendered video across all enabled platforms:
    1. YouTube Shorts (Google OAuth2 API)
    2. Instagram Reels (Meta Graph API)
    3. TikTok (TikTok Content Posting API v2)

    Gracefully skips any platform whose credentials are not yet configured in .env.
    Returns: Dict mapping platform names to published URLs/IDs.
    """
    logger.info("=================================================================")
    logger.info(f"STARTING MULTI-PLATFORM SYNDICATION FOR: {video_path.name}")
    logger.info(f"Dry-Run: {dry_run} | Variant: {ab_variant} | Privacy: {privacy}")
    logger.info("=================================================================")

    results: Dict[str, Optional[str]] = {
        "youtube": None,
        "instagram": None,
        "tiktok": None,
    }

    # 1. YouTube Shorts
    try:
        logger.info("[Platform 1/3] Uploading to YouTube Shorts...")
        results["youtube"] = upload_short_to_youtube(
            video_path=video_path,
            metadata=metadata,
            ab_variant=ab_variant,
            privacy=privacy,
            dry_run=dry_run,
        )
    except Exception as e:
        logger.error(f"YouTube publishing failed: {e}")

    # 2. Instagram Reels
    try:
        logger.info("[Platform 2/3] Uploading to Instagram Reels...")
        results["instagram"] = upload_reel_to_instagram(
            video_path=video_path,
            metadata=metadata,
            dry_run=dry_run,
        )
    except Exception as e:
        logger.error(f"Instagram publishing failed: {e}")

    # 3. TikTok
    try:
        logger.info("[Platform 3/3] Uploading to TikTok...")
        results["tiktok"] = upload_video_to_tiktok(
            video_path=video_path,
            metadata=metadata,
            dry_run=dry_run,
        )
    except Exception as e:
        logger.error(f"TikTok publishing failed: {e}")

    # Summary Log
    logger.info("=================================================================")
    logger.info("MULTI-PLATFORM SYNDICATION SUMMARY:")
    logger.info(f"  • YouTube Shorts:  {results['youtube'] or '❌ Skipped / Failed'}")
    logger.info(f"  • Instagram Reels: {results['instagram'] or '⚠️ Skipped (unconfigured)'}")
    logger.info(f"  • TikTok:          {results['tiktok'] or '⚠️ Skipped (unconfigured)'}")
    logger.info("=================================================================")

    return results
