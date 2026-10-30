#!/usr/bin/env python3
"""
YouTube Shorts Uploader via YouTube Data API v3 with OAuth2.
Handles resumable video uploads, metadata injection, and automated pinned comment posting.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

from common.env_loader import load_project_env

load_project_env()

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
logger = logging.getLogger("common.publishing.youtube")

SECRETS_DIR = Path(__file__).resolve().parent.parent.parent / "secrets"
_found_secret = SECRETS_DIR / "client_secret.json" if (SECRETS_DIR / "client_secret.json").exists() else SECRETS_DIR / "client_secrets.json"
DEFAULT_CLIENT_SECRETS = str(_found_secret)
DEFAULT_TOKEN_FILE = str(SECRETS_DIR / "youtube_token.json")

YOUTUBE_CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", DEFAULT_CLIENT_SECRETS)
YOUTUBE_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", DEFAULT_TOKEN_FILE)
DEFAULT_PRIVACY = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def get_authenticated_service():
    """Returns authenticated YouTube Data API client or None if unconfigured."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        logger.warning("Google API client not installed (google-api-python-client google-auth-oauthlib).")
        return None

    creds = None
    token_path = Path(YOUTUBE_TOKEN_FILE)

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), YOUTUBE_SCOPES)
        except Exception as e:
            logger.warning(f"Existing token file invalid: {e}")

    if creds and not creds.valid:
        if creds.refresh_token:
            try:
                from google.auth.transport.requests import Request
                logger.info("YouTube access token expired. Refreshing via refresh_token...")
                creds.refresh(Request())
                with open(token_path, "w", encoding="utf-8") as token_out:
                    token_out.write(creds.to_json())
            except Exception as e:
                logger.error(f"Failed to refresh YouTube OAuth token: {e}")
                creds = None
        else:
            creds = None

    if not creds:
        secrets_path = Path(YOUTUBE_CLIENT_SECRETS)
        if not secrets_path.exists():
            logger.warning(f"YouTube client_secrets file not found at {secrets_path}")
            return None
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception as e:
            logger.error(f"Failed to authenticate with YouTube: {e}")
            return None

    return build("youtube", "v3", credentials=creds)


def upload_short_to_youtube(
    video_path: Path,
    metadata: Dict[str, Any],
    privacy: Optional[str] = None,
    dry_run: bool = False,
) -> Optional[str]:
    """Uploads vertical MP4 to YouTube Shorts."""
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        return None

    privacy_status = (privacy or DEFAULT_PRIVACY).lower()
    if privacy_status not in ("public", "unlisted", "private"):
        privacy_status = "public"

    title = metadata.get("title", metadata.get("title_a", "Ayurvedic Insights #Shorts"))
    if "#Shorts" not in title and "#shorts" not in title:
        title = f"{title} #Shorts"
    title = title[:100]

    description = metadata.get("description", metadata.get("description_a", ""))
    tags = metadata.get("tags", ["Shorts", "Health", "Ayurveda"])

    if dry_run:
        logger.info(f"[DRY-RUN] Would upload {video_path.name} to YouTube Shorts:\n  Title: {title}")
        return "dry_run_yt_id"

    service = get_authenticated_service()
    if not service:
        logger.warning("YouTube service unauthenticated. Skipping YouTube upload.")
        return None

    try:
        from googleapiclient.http import MediaFileUpload

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "26",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)

        logger.info(f"Uploading {video_path.name} to YouTube...")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Upload progress: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        logger.info(f"Successfully uploaded to YouTube! Video ID: {video_id} (https://youtu.be/{video_id})")
        return video_id
    except Exception as e:
        logger.error(f"Failed to upload video to YouTube: {e}")
        return None
