"""
Central configuration for the autonomous Shorts clipping, publishing and monetization engine.
"""

import os
from pathlib import Path

# Try to load .env if present
try:
    from dotenv import load_dotenv
    PROJECT_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
    if PROJECT_ROOT_ENV.exists():
        load_dotenv(dotenv_path=PROJECT_ROOT_ENV)
except ImportError:
    pass

# --- Directory Paths ---
CLIPPING_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CLIPPING_DIR.parent
DATA_DIR = CLIPPING_DIR / "data"
OUTPUT_DIR = CLIPPING_DIR / "output_clips"
SECRETS_DIR = PROJECT_ROOT / "secrets"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SECRETS_DIR.mkdir(parents=True, exist_ok=True)

# --- Ollama Configuration ---
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_AUTH_TOKEN = os.getenv("OLLAMA_AUTH_TOKEN", "")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))

# --- YouTube OAuth & API ---
YOUTUBE_CLIENT_SECRETS = os.getenv(
    "YOUTUBE_CLIENT_SECRETS_FILE",
    str(SECRETS_DIR / "client_secrets.json")
)
YOUTUBE_TOKEN_FILE = os.getenv(
    "YOUTUBE_TOKEN_FILE",
    str(SECRETS_DIR / "youtube_token.json")
)
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

# --- Instagram Graph API Configuration ---
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")

# --- TikTok Content Posting API Configuration ---
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")
TIKTOK_PRIVACY_LEVEL = os.getenv("TIKTOK_PRIVACY_LEVEL", "PUBLIC_TO_EVERYONE")


# --- Cloud Storage (rclone) ---
GDRIVE_REMOTE = os.getenv(
    "RCLONE_CLIPS_REMOTE",
    "gdrive:TaskAutomation/clips-output/"
)

# --- Whisper Transcription ---
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")  # Auto-fallback to cpu handled in transcriber
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

# --- Niche Configuration: Business & Wealth Mindset ---
NICHE = "business_wealth"
NICHE_CONFIG = {
    "name": "Business & Wealth Mindset",
    "search_keywords": [
        "business advice entrepreneur interview",
        "wealth building strategy podcast",
        "how to make money online mentor",
        "startup founder story advice",
        "financial freedom investing tips",
        "billionaire mindset interview",
        "productivity habits high performance",
        "AI tools business automation",
        "side hustle ideas 2025",
        "entrepreneurship lessons learned",
    ],
    "category_id": "22",  # People & Blogs / Education
    "estimated_rpm": 0.20,
    "target_tags": [
        "business", "entrepreneur", "wealth", "money", "investing",
        "startup", "mindset", "motivation", "success", "finance",
        "side hustle", "passive income", "Shorts", "podcast",
    ],
}

# --- Content Blacklist Patterns (Prevent Copyright & Strikes) ---
BLACKLIST_PATTERNS = [
    r"(?i)(official\s*music\s*video|vevo|sony|universal|warner)",
    r"(?i)(full\s*movie|full\s*episode|netflix|disney|hbo)",
    r"(?i)(nfl|nba|fifa|premier\s*league|espn|sky\s*sports)",
    r"(?i)(copyright|all\s*rights\s*reserved|do\s*not\s*reupload)",
    r"(?i)(asmr|mukbang|unboxing|haul)",
]

# --- 6-Layer Transformative Shield Settings ---
STRIP_SOURCE_AUDIO = True          # ALWAYS True: source audio completely removed
REQUIRE_COMMENTARY = True          # ALWAYS True: original narration generated
COLOR_GRADE_HUE_SHIFT = 3         # Degrees hue rotation
COLOR_GRADE_SAT_BOOST = 1.08      # 8% saturation boost
KEN_BURNS_ZOOM_MAX = 1.06         # Subtle zoom endpoint
SUBTITLE_SCREEN_COVERAGE = 0.35   # Screen coverage of karaoke captions
MAX_CLIP_DURATION = 55            # YouTube Shorts limit is 60s
MIN_CLIP_DURATION = 28            # Minimum length for narrative complete arc
OPTIMAL_CLIP_DURATION = 40        # Sweet spot for retention

# --- Upload Schedule & Pacing ---
CLIPS_PER_DAY = 3
UPLOAD_TIMES_UTC = ["14:00", "17:30", "21:00"]
MIN_HOURS_BETWEEN_UPLOADS = 4

# --- Day-1 Monetization & Affiliate Links ---
BRIDGE_PAGE_URL = os.getenv("BRIDGE_PAGE_URL", "https://beacons.ai/samctec")
TELEGRAM_COMMUNITY_LINK = os.getenv(
    "TELEGRAM_FREE_INVITE_LINK",
    "https://t.me/your_business_channel"
)
AFFILIATE_LINKS = {
    "tools": os.getenv("AFFILIATE_TOOLS_LINK", "https://beacons.ai/samctec"),
    "books": os.getenv("AFFILIATE_BOOKS_LINK", "https://amzn.to/yourlist"),
    "newsletter": os.getenv("NEWSLETTER_SIGNUP_LINK", "https://yourname.substack.com"),
}

# --- Monetized Description & Pinned Comment Templates ---
DESCRIPTION_TEMPLATE = """{summary}

━━━━━━━━━━━━━━━━━━━━━━━━
🔥 FREE BUSINESS & WEALTH RESOURCES:
🔗 Free tools & software stack:
{bridge_page_url}

📱 Join our free entrepreneur community:
{telegram_link}

📧 Weekly business breakdown newsletter:
{newsletter_link}
━━━━━━━━━━━━━━━━━━━━━━━━

📌 Original content by {original_creator} — analyzed and shared for educational commentary.
⚠️ Editorial & transformative commentary only. Not financial or business advice.
Affiliate disclosure: Links above may earn a partner commission at no extra cost to you.

#Shorts #Business #Entrepreneur #Money #Wealth #Success"""

PINNED_COMMENT_TEMPLATE = """💬 What's YOUR biggest takeaway from this? Drop your thoughts below 👇

🔥 Get the full business tool stack & free templates → {bridge_page_url}"""
