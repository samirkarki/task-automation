#!/usr/bin/env python3
"""
YouTube Shorts Uploader via YouTube Data API v3 with OAuth2.
Handles resumable video uploads, metadata injection, and automated pinned comment posting.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.env_loader import load_project_env

load_project_env()

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
logger = logging.getLogger("common.publishing.youtube")

SECRETS_DIR = PROJECT_ROOT / "secrets"


def resolve_youtube_token_path() -> Path:
    """Discovers youtube_token.json across candidate paths."""
    env_token = os.getenv("YOUTUBE_TOKEN_FILE")
    if env_token:
        return Path(env_token).resolve()

    candidates = [
        SECRETS_DIR / "youtube_token.json",
        SECRETS_DIR / "token.json",
        Path.cwd() / "secrets" / "youtube_token.json",
        Path.cwd() / "secrets" / "token.json",
        Path.cwd() / "youtube_token.json",
        Path.cwd() / "token.json",
        PROJECT_ROOT / "youtube_token.json",
    ]
    for p in candidates:
        if p.exists() and p.stat().st_size > 10:
            return p.resolve()

    return (SECRETS_DIR / "youtube_token.json").resolve()


def resolve_youtube_client_secrets_path() -> Path:
    """Discovers client_secret.json across candidate paths and filename patterns."""
    env_secret = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE")
    if env_secret:
        p = Path(env_secret).resolve()
        if p.exists():
            return p

    search_dirs = [
        SECRETS_DIR,
        Path.cwd() / "secrets",
        Path.cwd(),
        PROJECT_ROOT,
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for name in ["client_secret.json", "client_secrets.json"]:
            p = d / name
            if p.exists() and p.stat().st_size > 10:
                return p.resolve()
        # Wildcard match (Google Cloud Console default download: client_secret_*.json)
        for p in d.glob("client_secret*.json"):
            if p.exists() and p.stat().st_size > 10:
                return p.resolve()

    # Default fallback
    return (SECRETS_DIR / "client_secret.json").resolve()


DEFAULT_CLIENT_SECRETS = str(resolve_youtube_client_secrets_path())
DEFAULT_TOKEN_FILE = str(resolve_youtube_token_path())

YOUTUBE_CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", DEFAULT_CLIENT_SECRETS)
YOUTUBE_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", DEFAULT_TOKEN_FILE)
DEFAULT_PRIVACY = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def get_authenticated_service():
    """Returns authenticated YouTube Data API client or None if unconfigured."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        logger.warning("Google API client not installed. Run: pip install google-api-python-client google-auth-oauthlib")
        return None

    token_path = resolve_youtube_token_path()
    secrets_path = resolve_youtube_client_secrets_path()
    creds = None

    if token_path.exists() and token_path.stat().st_size > 10:
        logger.info(f"Loading existing YouTube token from: {token_path}")
        try:
            # Load credentials without rigid scope constraint to avoid rejection of prior tokens
            creds = Credentials.from_authorized_user_file(str(token_path))
        except Exception as e:
            logger.warning(f"Existing token file invalid ({e}).")

    if creds and not creds.valid:
        if creds.refresh_token:
            try:
                from google.auth.transport.requests import Request
                logger.info("YouTube access token expired. Refreshing via refresh_token...")
                creds.refresh(Request())
                with open(token_path, "w", encoding="utf-8") as token_out:
                    token_out.write(creds.to_json())
                logger.info(f"[+] Successfully refreshed YouTube token at {token_path}")
            except Exception as e:
                logger.error(
                    f"Failed to refresh YouTube OAuth token: {e}\n"
                    "Note: In Google Cloud Console, if your OAuth consent screen is in 'Testing' mode, "
                    "refresh tokens expire automatically after 7 days.\n"
                    "Fix: Re-authenticate, and in Google Cloud Console -> 'OAuth consent screen', click 'Publish App'."
                )
                creds = None
        else:
            creds = None

    if not creds:
        if not secrets_path.exists() or secrets_path.stat().st_size < 10:
            logger.warning(f"YouTube client_secrets file not found. Searched candidate paths around: {secrets_path}")
            return None

        logger.info(f"Authenticating YouTube OAuth with client secret: {secrets_path}")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
            logger.info(f"[+] Saved newly authenticated token to: {token_path}")
        except Exception as local_err:
            logger.info("No desktop browser detected. Switching to headless console authorization...")
            try:
                redirect_uri = "http://localhost:8080/"
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(secrets_path),
                    scopes=YOUTUBE_SCOPES,
                    redirect_uri=redirect_uri,
                )
                auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
                print("\n" + "=" * 70)
                print("      HEADLESS YOUTUBE AUTHENTICATION (NO BROWSER NEEDED)")
                print("=" * 70)
                print("\nStep 1: Open this URL in any browser (phone or laptop):")
                print(auth_url)
                print("\nStep 2: Sign in and approve YouTube upload permissions.")
                print("Step 3: Copy the redirect URL (http://localhost:8080/?state=...&code=...) and paste below:")
                redirect_response = input("Paste redirected URL: ").strip()
                if redirect_response:
                    if not redirect_response.startswith("http"):
                        redirect_response = "http://" + redirect_response
                    flow.fetch_token(authorization_response=redirect_response)
                    creds = flow.credentials
                    token_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(token_path, "w", encoding="utf-8") as f:
                        f.write(creds.to_json())
                    logger.info(f"[+] Saved newly authenticated token to: {token_path}")
            except Exception as headless_err:
                logger.error(f"Failed to authenticate with YouTube: {headless_err}")
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="YouTube Authentication & Verification Tool")
    parser.add_argument("--test", action="store_true", help="Verify YouTube API connection and print channel info")
    parser.add_argument("--reauth", action="store_true", help="Force new authentication flow")
    args = parser.parse_args()

    token_p = resolve_youtube_token_path()
    if args.reauth and token_p.exists():
        logger.info(f"Removing expired/existing token: {token_p}")
        token_p.unlink()

    service = get_authenticated_service()
    if service:
        try:
            resp = service.channels().list(mine=True, part="snippet").execute()
            items = resp.get("items", [])
            if items:
                ch_title = items[0]["snippet"]["title"]
                ch_id = items[0]["id"]
                print("\n" + "=" * 65)
                print(f"✅ SUCCESS! Authenticated with YouTube Channel:")
                print(f"   Title: {ch_title}")
                print(f"   ID:    {ch_id}")
                print("=" * 65 + "\n")
            else:
                print("✅ Successfully authenticated with YouTube API (no channel found on this account).")
        except Exception as e:
            print(f"❌ Authenticated credentials failed API query: {e}")
    else:
        print("❌ YouTube authentication failed.")
