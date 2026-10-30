#!/usr/bin/env python3
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

from common.env_loader import load_project_env

load_project_env()

logger = logging.getLogger("common.publishing.tiktok")

TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
TIKTOK_PRIVACY_LEVEL = os.getenv("TIKTOK_PRIVACY_LEVEL", "PUBLIC_TO_EVERYONE").strip()

INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


def upload_video_to_tiktok(
    video_path: Path,
    metadata: Dict[str, Any],
    dry_run: bool = False,
) -> Optional[str]:
    """Publishes a vertical MP4 video to TikTok via Content Posting API v2."""
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        logger.error(f"Target video file not found for TikTok: {video_path}")
        return None

    if not TIKTOK_ACCESS_TOKEN:
        logger.warning("TikTok access token unconfigured (TIKTOK_ACCESS_TOKEN). Skipping TikTok upload.")
        return None

    title = metadata.get("title", metadata.get("title_a", "Ayurveda Tips"))
    tags = metadata.get("tags", ["ayurveda", "health", "wellness"])
    hashtags = " ".join([f"#{t.replace(' ', '').lower()}" for t in tags][:5])
    caption = f"{title}\n\n{hashtags}"[:2000].strip()

    if dry_run:
        logger.info(f"[DRY-RUN] Would upload {video_path.name} to TikTok.")
        return "dry_run_tiktok_id"

    file_size = video_path.stat().st_size
    headers = {
        "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    init_payload = {
        "post_info": {
            "title": caption,
            "privacy_level": TIKTOK_PRIVACY_LEVEL,
            "disable_duet": False,
            "disable_stitch": False,
            "disable_comment": False,
            "video_cover_timestamp_ms": 1000,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,
            "total_chunk_count": 1,
        },
    }

    try:
        init_resp = requests.post(INIT_URL, headers=headers, json=init_payload, timeout=30)
        init_data = init_resp.json()
        if init_data.get("error", {}).get("code") != "ok":
            logger.error(f"TikTok init failed: {init_data}")
            return None

        publish_id = init_data["data"]["publish_id"]
        upload_url = init_data["data"]["upload_url"]

        with open(video_path, "rb") as vf:
            video_bytes = vf.read()

        up_headers = {
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
        }
        up_resp = requests.put(upload_url, headers=up_headers, data=video_bytes, timeout=120)
        if up_resp.status_code not in (200, 201):
            logger.error(f"TikTok binary upload failed: HTTP {up_resp.status_code}")
            return None

        logger.info(f"Successfully uploaded to TikTok! Publish ID: {publish_id}")
        return publish_id

    except Exception as e:
        logger.error(f"Error publishing to TikTok: {e}")
        return None
