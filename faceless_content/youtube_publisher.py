#!/usr/bin/env python3
"""
YouTube Shorts Auto-Publisher
Uploads generated 9:16 vertical MP4 videos to YouTube Shorts using YouTube Data API v3.
Injects SEO-optimized descriptions, tags, and automated monetization links:
- Telegram Free Signals Community Link
- Demat / TMS Broker Affiliate Link
- Compliance Disclaimer
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("youtube_publisher")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SECRETS_DIR = Path(__file__).resolve().parent.parent / "secrets"
CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", str(SECRETS_DIR / "client_secrets.json"))
TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", str(SECRETS_DIR / "youtube_token.json"))

TELEGRAM_FREE_INVITE_LINK = os.getenv("TELEGRAM_FREE_INVITE_LINK", "https://t.me/your_nepse_channel")
AFFILIATE_BROKER_LINK = os.getenv("AFFILIATE_BROKER_LINK", "https://nepsetms.com/referral")
AFFILIATE_BOOK_LINK = os.getenv("AFFILIATE_BOOK_LINK", "https://amzn.to/example")
DEFAULT_PRIVACY = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
MANDATORY_DISCLAIMER = "Automated data research only. Not financial advice."

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


# -----------------------------------------------------------------------------
# Description & Metadata Formatter
# -----------------------------------------------------------------------------
def build_shorts_metadata(
    topic: str,
    video_summary: Optional[str] = None,
    tags: Optional[List[str]] = None,
    privacy: str = DEFAULT_PRIVACY,
) -> Dict[str, Any]:
    """
    Builds high-CTR title, description, and tags for YouTube Shorts.
    """
    clean_topic = topic.strip().replace("#", "")
    # Title must include #Shorts to ensure YouTube categorizes it as a Short
    title = f"{clean_topic} 📈 #Shorts #NEPSE"
    if len(title) > 95:
        title = f"{clean_topic[:75]}... #Shorts #NEPSE"

    default_tags = [
        "NEPSE", "Nepal Stock Exchange", "Share Market Nepal", "NEPSE Analysis",
        "Stock Market", "Trading Strategy", "NEPSE Update", "Shorts", "Finance"
    ]
    if tags:
        default_tags = list(set(default_tags + tags))

    description = f"""{clean_topic}

💡 Real-time quantitative data and AI analysis on the Nepal Stock Exchange (NEPSE).

━━━━━━━━━━━━━━━━━━━━━━━━
🔥 CONNECT & TRADE SMARTER:
👉 Join our FREE Telegram Channel for daily morning signals:
{TELEGRAM_FREE_INVITE_LINK}

📈 Open your Demat & TMS Trading Account:
{AFFILIATE_BROKER_LINK}

📚 Recommended Books for Serious Stock Traders:
{AFFILIATE_BOOK_LINK}
━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ DISCLAIMER:
{MANDATORY_DISCLAIMER}
For educational and data research purposes only. Always consult a certified financial advisor before investing.

#NEPSE #ShareMarketNepal #NepalStockExchange #FinanceShorts #TradingStrategy
"""

    return {
        "snippet": {
            "title": title,
            "description": description.strip(),
            "tags": default_tags,
            "categoryId": "27",  # Education
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }


# -----------------------------------------------------------------------------
# YouTube API Authentication & Upload
# -----------------------------------------------------------------------------
def get_authenticated_service():
    """
    Authenticates with YouTube API via OAuth2.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        logger.warning(
            "Google API libraries not installed. Run 'pip install google-api-python-client google-auth-oauthlib'."
        )
        return None

    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            logger.warning(f"Existing token file invalid ({e}).")

    if not creds or not creds.valid:
        if not os.path.exists(CLIENT_SECRETS_FILE):
            logger.warning(
                f"[YOUTUBE] client_secrets.json not found at '{CLIENT_SECRETS_FILE}'. "
                "Download OAuth2 Desktop client secrets from Google Cloud Console to enable live uploads."
            )
            return None

        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def publish_short_video(
    video_path: Path,
    topic: str,
    tags: Optional[List[str]] = None,
    privacy: str = DEFAULT_PRIVACY,
    dry_run: bool = False,
) -> Optional[str]:
    """
    Uploads vertical video to YouTube Shorts.
    """
    if not video_path.exists():
        logger.error(f"Target video file does not exist: {video_path}")
        return None

    metadata = build_shorts_metadata(topic, tags=tags, privacy=privacy)

    if dry_run:
        logger.info("[YOUTUBE DRY-RUN] Metadata prepared successfully:")
        logger.info(json.dumps(metadata, indent=2))
        logger.info(f"[YOUTUBE DRY-RUN] Would upload: {video_path.name} ({video_path.stat().st_size / (1024*1024):.2f} MB)")
        return "DRY_RUN_SUCCESS"

    service = get_authenticated_service()
    if not service:
        logger.warning("[YOUTUBE] Service unauthenticated. Operating in dry-run mode.")
        logger.info(f"Generated metadata:\nTitle: {metadata['snippet']['title']}")
        return None

    from googleapiclient.http import MediaFileUpload

    logger.info(f"Initiating YouTube upload for {video_path.name}...")
    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")

    request = service.videos().insert(
        part="snippet,status",
        body=metadata,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info(f"Uploaded {int(status.progress() * 100)}%...")

    video_id = response.get("id")
    video_url = f"https://youtube.com/shorts/{video_id}"
    logger.info(f"Successfully uploaded to YouTube Shorts: {video_url}")
    return video_url


def main():
    parser = argparse.ArgumentParser(description="YouTube Shorts Auto-Publisher")
    parser.add_argument("--video", type=Path, default=None, help="Path to .mp4 video file.")
    parser.add_argument("--topic", type=str, default="NEPSE Market Secrets", help="Video topic.")
    parser.add_argument("--dry-run", action="store_true", help="Print metadata without live upload.")

    args = parser.parse_args()

    if args.video and args.video.exists():
        publish_short_video(args.video, topic=args.topic, dry_run=args.dry_run)
    else:
        logger.info("Running metadata test with dry-run...")
        dummy_path = Path("test_video.mp4")
        if not dummy_path.exists():
            dummy_path.touch()
        publish_short_video(dummy_path, topic=args.topic, dry_run=True)
        dummy_path.unlink()


if __name__ == "__main__":
    main()
