"""
TikTok Direct Video Uploader via Official TikTok Content Posting API v2.
Publishes vertical MP4 videos directly to TikTok using chunked binary upload.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
import requests

from clipping.config import (
    TIKTOK_ACCESS_TOKEN,
    TIKTOK_PRIVACY_LEVEL,
    BRIDGE_PAGE_URL,
)

logger = logging.getLogger("clipping.publishing.tiktok_uploader")

INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


def format_tiktok_title(metadata: Dict[str, Any]) -> str:
    """Formats a punchy title and trending hashtags for TikTok's algorithm."""
    raw_title = metadata.get("title_a", "").replace("#Shorts", "").strip()
    tags = metadata.get("tags", ["business", "money", "mindset", "success"])
    hashtags = " ".join([f"#{t.replace(' ', '').lower()}" for t in tags if t.lower() != "shorts"][:5])

    # TikTok allows up to 2200 characters in caption, but clean punchy hooks convert best
    caption = f"{raw_title}\n\nFree tools & templates in bio! #fyp #viral {hashtags}"
    return caption[:2000].strip()


def upload_video_to_tiktok(
    video_path: Path,
    metadata: Dict[str, Any],
    dry_run: bool = False,
) -> Optional[str]:
    """
    Publishes a vertical MP4 video to TikTok via the official Content Posting API v2.
    Returns: Publish ID or TikTok video URL if successful, None otherwise.
    """
    if not video_path.exists():
        logger.error(f"Target video file not found for TikTok: {video_path}")
        return None

    caption = format_tiktok_title(metadata)
    file_size = video_path.stat().st_size

    if dry_run:
        logger.info("[TIKTOK DRY-RUN] Video prepared successfully:")
        logger.info(f"  File: {video_path.name} ({file_size / (1024 * 1024):.2f} MB)")
        logger.info(f"  Caption: {caption[:120]}...")
        return f"https://www.tiktok.com/@user/video/DRY_RUN_{video_path.stem}"

    if not TIKTOK_ACCESS_TOKEN:
        logger.info("TikTok access token not configured in .env (TIKTOK_ACCESS_TOKEN). Skipping TikTok upload.")
        return None

    headers = {
        "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    init_payload = {
        "post_info": {
            "title": caption,
            "privacy_level": TIKTOK_PRIVACY_LEVEL,
            "disable_comment": False,
            "disable_duet": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1,
        },
    }

    logger.info(f"Initiating TikTok direct post initialization for {video_path.name} ({file_size / (1024*1024):.2f} MB)...")

    try:
        # Step 1: Initialize Post
        res = requests.post(INIT_URL, headers=headers, json=init_payload, timeout=30)
        res_data = res.json()

        if res.status_code != 200 or res_data.get("error", {}).get("code") != "ok":
            logger.error(f"TikTok post initialization failed: {res_data}")
            return None

        data = res_data.get("data", {})
        upload_url = data.get("upload_url")
        publish_id = data.get("publish_id")

        if not upload_url or not publish_id:
            logger.error(f"TikTok init missing upload_url or publish_id: {res_data}")
            return None

        # Step 2: Upload Binary Video via PUT
        logger.info(f"Streaming binary video chunk to TikTok upload endpoint...")
        put_headers = {
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            "Content-Type": "video/mp4",
        }

        with open(video_path, "rb") as f:
            upload_res = requests.put(upload_url, headers=put_headers, data=f, timeout=120)

        if upload_res.status_code not in [200, 201]:
            logger.error(f"TikTok binary chunk upload failed (HTTP {upload_res.status_code}): {upload_res.text}")
            return None

        logger.info(f"Binary transfer complete. Polling publish status for ID: {publish_id}...")

        # Step 3: Check Publish Status
        status_payload = {"publish_id": publish_id}
        for _ in range(12):  # Poll up to 60 seconds
            time.sleep(5)
            status_res = requests.post(STATUS_URL, headers=headers, json=status_payload, timeout=20)
            status_json = status_res.json()

            if status_json.get("error", {}).get("code") == "ok":
                status = status_json.get("data", {}).get("status")
                if status == "PUBLISH_COMPLETE":
                    logger.info(f"✅ Video successfully published to TikTok! (Publish ID: {publish_id})")
                    return f"https://www.tiktok.com/@user/video/{publish_id}"
                elif status == "FAILED":
                    fail_reason = status_json.get("data", {}).get("fail_reason")
                    logger.error(f"TikTok publishing failed: {fail_reason}")
                    return None
                else:
                    logger.info(f"TikTok processing status: {status}. Waiting...")
            else:
                logger.warning(f"Status check returned warning: {status_json}")

        # If still processing asynchronously, return the publish ID reference
        logger.info(f"Video uploaded and pending final processing by TikTok (Publish ID: {publish_id}).")
        return f"https://www.tiktok.com/@user/video/{publish_id}"

    except Exception as e:
        logger.error(f"Error publishing to TikTok: {e}", exc_info=True)
        return None
