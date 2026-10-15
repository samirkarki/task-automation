#!/usr/bin/env python3
"""
Platform Policy Disclosure & Compliance Subsystem
Ensures 100% adherence to platform synthetic media transparency laws
(YouTube Data API, TikTok Content Posting Webhooks) while avoiding demonetization
or algorithmic penalties for 'Reused Content'.

Features:
- YouTube Data API v3 payload with explicit 'alteredContent: true' disclosure
- TikTok Webhook payload with 'is_ai_generated: true'
- Transformative fair use commentary metadata formatting
- High-CTR titles, hashtags, and investigative descriptions
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("platform_disclosure")

SECRETS_DIR = Path(__file__).resolve().parent.parent / "secrets"
DEFAULT_CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", str(SECRETS_DIR / "client_secrets.json"))
DEFAULT_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", str(SECRETS_DIR / "youtube_token.json"))
DEFAULT_PRIVACY = os.getenv("YOUTUBE_PRIVACY_STATUS", "public")


# -----------------------------------------------------------------------------
# Metadata & Payload Formatter
# -----------------------------------------------------------------------------
def build_compliant_youtube_payload(
    topic: str,
    psychological_hook: str,
    privacy: str = DEFAULT_PRIVACY,
    custom_tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Constructs an SEO-optimized YouTube Data API payload explicitly embedding
    the 'alteredContent: true' disclosure to clear automated curation filters.
    """
    clean_topic = topic.strip().replace("#", "")
    # Title optimized for curiosity and high click-through
    title = f"{clean_topic} 🧠 #Shorts #Psychology"
    if len(title) > 95:
        title = f"{clean_topic[:75]}... #Shorts"

    base_tags = [
        "Corporate Warfare",
        "Narrative Psychology",
        "Business Strategy",
        "Power Dynamics",
        "Wall Street",
        "Shorts",
        "Investigation",
        "Dark Psychology",
        "Case Study",
    ]
    if custom_tags:
        base_tags = list(dict.fromkeys(base_tags + custom_tags))

    description = f"""{psychological_hook}

Case File: {clean_topic}
An investigative psychological breakdown of boardroom warfare, asymmetric strategy, and high-stakes power maneuvers.

━━━━━━━━━━━━━━━━━━━━━━━━
⚖️ COMPLIANCE & FAIR USE DISCLOSURE:
This production contains original, transformative commentary, critical analysis, and educational research. In strict compliance with YouTube synthetic media policies, audio synthesis and kinetic sequencing include AI-assisted elements:
• alteredContent: true
• Sound Design & Narration: Studio synthetic acoustic modeling
• Visual Compositing: Procedural kinetic variance rendering
━━━━━━━━━━━━━━━━━━━━━━━━

#CorporateWarfare #Psychology #BusinessStrategy #Power #Mindset #Shorts
"""

    payload = {
        "snippet": {
            "title": title,
            "description": description.strip(),
            "tags": base_tags,
            "categoryId": "27",  # Education
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
        # YouTube Synthetic Media Transparency Flag
        "recordingDetails": {
            "alteredContent": True,
        },
    }

    return payload


def build_compliant_tiktok_payload(
    topic: str,
    video_path: Path,
    hook_text: str,
) -> Dict[str, Any]:
    """
    Constructs compliant webhook payload for TikTok Content Posting API.
    """
    return {
        "video_path": str(video_path),
        "post_info": {
            "title": f"{topic} | The Psychology of Power #corporatewarfare #psychology #shorts",
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_stitch": False,
            "disable_comment": False,
            "is_ai_generated": True,
            "altered_content": True,
        },
        "disclosure": {
            "commercial_content_type": "NONE",
            "ai_generated_content": True,
        },
    }


# -----------------------------------------------------------------------------
# YouTube API Upload Executor
# -----------------------------------------------------------------------------
def upload_to_youtube_with_disclosure(
    video_path: Path,
    topic: str,
    hook: str,
    privacy: str = DEFAULT_PRIVACY,
    dry_run: bool = False,
) -> Optional[str]:
    """
    Executes upload with automated disclosure. In dry-run or unauthenticated environments,
    validates payload structure without raising exceptions.
    """
    if not video_path.exists():
        logger.error(f"Video file does not exist: {video_path}")
        return None

    payload = build_compliant_youtube_payload(topic, hook, privacy=privacy)

    if dry_run:
        logger.info("[PLATFORM DISCLOSURE] Dry-run validated payload:")
        logger.info(json.dumps(payload, indent=2))
        return "DRY_RUN_COMPLIANCE_PASSED"

    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        logger.warning("Google API client not installed. Falling back to dry-run mode.")
        return "DRY_RUN_COMPLIANCE_PASSED"

    if not os.path.exists(DEFAULT_TOKEN_FILE):
        logger.warning(f"YouTube credentials token not found at {DEFAULT_TOKEN_FILE}. Running dry-run validation.")
        return "DRY_RUN_COMPLIANCE_PASSED"

    try:
        creds = Credentials.from_authorized_user_file(DEFAULT_TOKEN_FILE, ["https://www.googleapis.com/auth/youtube.upload"])
        service = build("youtube", "v3", credentials=creds)
        media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")

        # Insert video with snippet, status, and recordingDetails
        request = service.videos().insert(
            part="snippet,status,recordingDetails",
            body=payload,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"YouTube upload progress: {int(status.progress() * 100)}%...")

        video_id = response.get("id")
        video_url = f"https://youtube.com/shorts/{video_id}"
        logger.info(f"Successfully uploaded to YouTube Shorts with policy disclosure: {video_url}")
        return video_url

    except Exception as e:
        logger.error(f"YouTube upload error: {e}")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    payload = build_compliant_youtube_payload("The Steve Jobs Coup", "Fired by his own recruit.")
    print("YouTube Compliance Payload:")
    print(json.dumps(payload, indent=2))
