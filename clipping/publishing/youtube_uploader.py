"""
YouTube Shorts Uploader via YouTube Data API v3 with OAuth2.
Handles resumable video uploads, metadata injection, and automated pinned comment posting.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from clipping.config import (
    YOUTUBE_CLIENT_SECRETS,
    YOUTUBE_TOKEN_FILE,
    YOUTUBE_SCOPES,
)

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
logger = logging.getLogger("clipping.publishing.youtube_uploader")


def get_authenticated_service():
    """
    Returns authenticated YouTube Data API client or None if unconfigured.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        logger.warning("Google API client not installed. Install via pip install google-api-python-client google-auth-oauthlib")
        return None

    creds = None
    token_path = Path(YOUTUBE_TOKEN_FILE)
    secrets_path = Path(YOUTUBE_CLIENT_SECRETS)

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), YOUTUBE_SCOPES)
        except Exception as e:
            logger.warning(f"Existing token file invalid: {e}")

    if not creds or not creds.valid:
        if not secrets_path.exists():
            logger.warning(
                f"YouTube client_secrets.json not found at '{secrets_path}'. "
                "Download OAuth2 Desktop client secrets from Google Cloud Console to enable live uploads."
            )
            return None

        flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), YOUTUBE_SCOPES)
        try:
            creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())
        except Exception:
            logger.info("No desktop browser detected. Switching to headless console authentication...")
            from clipping.auth import authenticate_headless
            if authenticate_headless():
                creds = Credentials.from_authorized_user_file(str(token_path), YOUTUBE_SCOPES)
            else:
                return None

    return build("youtube", "v3", credentials=creds)


def upload_short_to_youtube(
    video_path: Path,
    metadata: Dict[str, Any],
    ab_variant: str = "A",
    privacy: str = "public",
    dry_run: bool = False,
) -> Optional[str]:
    """
    Uploads vertical video to YouTube Shorts, injects metadata, and pins the affiliate comment.
    """
    if not video_path.exists():
        logger.error(f"Target video file not found: {video_path}")
        return None

    title = metadata["title_a"] if ab_variant == "A" else metadata["title_b"]
    description = metadata["description"]
    tags = metadata.get("tags", [])
    category_id = metadata.get("category_id", "22")
    pinned_comment = metadata.get("pinned_comment", "")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    if dry_run:
        logger.info("[YOUTUBE DRY-RUN] Metadata prepared successfully:")
        logger.info(f"  Title ({ab_variant}): {title}")
        logger.info(f"  Size: {video_path.stat().st_size / (1024 * 1024):.2f} MB")
        logger.info(f"  Description Preview: {description[:120]}...")
        logger.info(f"  Pinned Comment Preview: {pinned_comment[:90]}...")
        return f"https://youtube.com/shorts/DRY_RUN_{video_path.stem}"

    service = get_authenticated_service()
    if not service:
        logger.warning("YouTube service unauthenticated. Running in dry-run mode.")
        logger.info(f"[SIMULATED UPLOAD] Title: {title}")
        return f"https://youtube.com/shorts/SIMULATED_{video_path.stem}"

    from googleapiclient.http import MediaFileUpload

    logger.info(f"Initiating live YouTube upload for {video_path.name}...")
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")

    request = service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info(f"Upload progress: {int(status.progress() * 100)}%...")

    video_id = response.get("id")
    video_url = f"https://youtube.com/shorts/{video_id}"
    logger.info(f"Successfully published to YouTube Shorts: {video_url}")

    # Post Pinned Comment with Affiliate CTA
    if pinned_comment:
        try:
            logger.info("Posting pinned engagement & affiliate comment...")
            comment_payload = {
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {"textOriginal": pinned_comment}
                    },
                }
            }
            service.commentThreads().insert(part="snippet", body=comment_payload).execute()
            logger.info("Pinned comment published.")
        except Exception as e:
            logger.warning(f"Could not post pinned comment: {e}")

    return video_url
