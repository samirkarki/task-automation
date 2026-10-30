#!/usr/bin/env python3
"""
Instagram Reels Uploader via Meta Graph API v19.0+.
Publishes vertical MP4 videos directly to Instagram as Reels.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
import requests

from common.env_loader import load_project_env

load_project_env()

logger = logging.getLogger("common.publishing.instagram")

INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
GRAPH_API_VERSION = "v19.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def upload_reel_to_instagram(
    video_path: Path,
    metadata: Dict[str, Any],
    video_public_url: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[str]:
    """Publishes a vertical MP4 video as an Instagram Reel."""
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        return None

    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        logger.warning("Instagram credentials unconfigured (INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_ACCOUNT_ID). Skipping.")
        return None

    caption = metadata.get("description", metadata.get("title", ""))[:2200]

    if dry_run:
        logger.info(f"[DRY-RUN] Would upload {video_path.name} to Instagram Reel.")
        return "dry_run_ig_id"

    # Meta Graph API requires public URL or hosted binary
    if not video_public_url:
        logger.warning("Instagram Graph API requires a publicly accessible video URL. Skipping.")
        return None

    try:
        # Step 1: Create media container
        init_url = f"{BASE_URL}/{INSTAGRAM_ACCOUNT_ID}/media"
        payload = {
            "media_type": "REELS",
            "video_url": video_public_url,
            "caption": caption,
            "access_token": INSTAGRAM_ACCESS_TOKEN,
        }
        resp = requests.post(init_url, data=payload, timeout=30)
        resp_data = resp.json()
        container_id = resp_data.get("id")
        if not container_id:
            logger.error(f"Failed to create Instagram container: {resp_data}")
            return None

        # Step 2: Poll container status
        status_url = f"{BASE_URL}/{container_id}"
        status_params = {"fields": "status_code", "access_token": INSTAGRAM_ACCESS_TOKEN}
        for _ in range(30):
            time.sleep(5)
            s_resp = requests.get(status_url, params=status_params, timeout=15)
            code = s_resp.json().get("status_code")
            if code == "FINISHED":
                break
            elif code == "ERROR":
                logger.error(f"Instagram media processing failed: {s_resp.json()}")
                return None

        # Step 3: Publish container
        pub_url = f"{BASE_URL}/{INSTAGRAM_ACCOUNT_ID}/media_publish"
        pub_resp = requests.post(pub_url, data={"creation_id": container_id, "access_token": INSTAGRAM_ACCESS_TOKEN}, timeout=30)
        media_id = pub_resp.json().get("id")
        logger.info(f"Successfully published Instagram Reel! Media ID: {media_id}")
        return media_id

    except Exception as e:
        logger.error(f"Error publishing to Instagram: {e}")
        return None
