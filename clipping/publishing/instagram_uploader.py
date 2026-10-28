"""
Instagram Reels Direct Uploader via Meta Graph API.
Uses official resumable upload protocol to publish 9:16 vertical videos directly to Instagram Professional / Creator accounts.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
import requests

from clipping.config import (
    INSTAGRAM_ACCESS_TOKEN,
    INSTAGRAM_ACCOUNT_ID,
    BRIDGE_PAGE_URL,
)

logger = logging.getLogger("clipping.publishing.instagram_uploader")

API_VERSION = "v19.0"


def format_instagram_caption(metadata: Dict[str, Any]) -> str:
    """Formats an Instagram-optimized caption with hooks and niche hashtags."""
    title = metadata.get("title_a", "").replace("#Shorts", "").strip()
    tags = metadata.get("tags", ["business", "mindset", "wealth", "entrepreneur"])
    hashtag_str = " ".join([f"#{t.replace(' ', '').lower()}" for t in tags if t.lower() != "shorts"])

    caption = (
        f"{title}\n\n"
        f"Drop your thoughts below 👇\n\n"
        f"🔥 Free business resources & tools → link in bio ({BRIDGE_PAGE_URL})\n\n"
        f"•\n•\n•\n"
        f"#reels #viral {hashtag_str}"
    )
    return caption.strip()


def upload_reel_to_instagram(
    video_path: Path,
    metadata: Dict[str, Any],
    dry_run: bool = False,
) -> Optional[str]:
    """
    Publishes a vertical MP4 video to Instagram Reels via the Meta Graph API.
    Returns: Permalink or media ID if successful, None otherwise.
    """
    if not video_path.exists():
        logger.error(f"Target video file not found for Instagram: {video_path}")
        return None

    caption = format_instagram_caption(metadata)

    if dry_run:
        logger.info("[INSTAGRAM DRY-RUN] Reel prepared successfully:")
        logger.info(f"  File: {video_path.name} ({video_path.stat().st_size / (1024 * 1024):.2f} MB)")
        logger.info(f"  Caption Preview: {caption[:120]}...")
        return f"https://www.instagram.com/reel/DRY_RUN_{video_path.stem}"

    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        logger.info("Instagram credentials not configured in .env (INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID). Skipping Instagram upload.")
        return None

    file_size = video_path.stat().st_size
    init_url = f"https://graph.facebook.com/{API_VERSION}/{INSTAGRAM_ACCOUNT_ID}/media"

    logger.info(f"Initiating Instagram Reels resumable upload for {video_path.name} ({file_size / (1024*1024):.2f} MB)...")

    # Step 1: Initialize Resumable Upload Session
    init_payload = {
        "access_token": INSTAGRAM_ACCESS_TOKEN,
        "upload_type": "resumable",
        "media_type": "REELS",
        "caption": caption,
    }

    try:
        init_res = requests.post(init_url, data=init_payload, timeout=30)
        init_data = init_res.json()

        if "id" not in init_data and "uri" not in init_data:
            logger.error(f"Instagram upload initialization failed: {init_data}")
            return None

        container_id = init_data.get("id")
        upload_url = init_data.get("uri")

        if not upload_url:
            # Fallback to standard rupload endpoint for Meta Graph API
            upload_url = f"https://rupload.facebook.com/ig-reels-upload/{container_id}"

        # Step 2: Upload Binary Video Stream
        logger.info(f"Transferring binary video stream to Meta rupload endpoint...")
        headers = {
            "Authorization": f"OAuth {INSTAGRAM_ACCESS_TOKEN}",
            "file_offset": "0",
        }

        with open(video_path, "rb") as f:
            upload_res = requests.post(upload_url, headers=headers, data=f, timeout=120)

        if upload_res.status_code not in [200, 201]:
            logger.error(f"Video binary transfer to Instagram failed: {upload_res.text}")
            return None

        # Step 3: Wait for Video Processing
        logger.info("Waiting for Instagram to process video container...")
        status_url = f"https://graph.facebook.com/{API_VERSION}/{container_id}"
        is_ready = False

        for _ in range(20):  # Poll up to 100 seconds
            time.sleep(5)
            check_res = requests.get(status_url, params={"fields": "status_code", "access_token": INSTAGRAM_ACCESS_TOKEN}, timeout=20)
            status_data = check_res.json()
            code = status_data.get("status_code")

            if code == "FINISHED":
                is_ready = True
                break
            elif code in ["ERROR", "EXPIRED"]:
                logger.error(f"Instagram media processing failed: {status_data}")
                return None
            else:
                logger.info(f"Processing status: {code}. Retrying in 5s...")

        if not is_ready:
            logger.warning("Instagram processing timed out. Attempting publish anyway...")

        # Step 4: Publish Reel
        logger.info(f"Publishing container {container_id} to Instagram feed...")
        publish_url = f"https://graph.facebook.com/{API_VERSION}/{INSTAGRAM_ACCOUNT_ID}/media_publish"
        pub_res = requests.post(publish_url, data={"creation_id": container_id, "access_token": INSTAGRAM_ACCESS_TOKEN}, timeout=30)
        pub_data = pub_res.json()

        media_id = pub_data.get("id")
        if not media_id:
            logger.error(f"Instagram publishing failed: {pub_data}")
            return None

        reel_url = f"https://www.instagram.com/reel/{media_id}"
        logger.info(f"✅ Successfully published Instagram Reel: {reel_url}")
        return reel_url

    except Exception as e:
        logger.error(f"Error publishing to Instagram: {e}", exc_info=True)
        return None
