"""
Headless Authentication Helper for Ubuntu / SSH / Cloud Servers.
Allows authenticating with YouTube without needing a graphical desktop browser.
"""

import json
import logging
import os
import sys
from pathlib import Path

# Allow HTTP callback on localhost for headless OAuth
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from clipping.config import YOUTUBE_CLIENT_SECRETS, YOUTUBE_TOKEN_FILE, YOUTUBE_SCOPES

logger = logging.getLogger("clipping.auth")


def authenticate_headless():
    """
    Performs OAuth2 authentication in a headless terminal:
    1. Generates Google authorization URL.
    2. User opens the URL on any device (phone, laptop browser).
    3. User grants access; browser redirects to http://localhost:8080/?state=...&code=...
    4. User copies that redirect URL from their browser address bar and pastes it into this terminal.
    5. Exchanges code for token and saves secrets/youtube_token.json.
    """
    secrets_path = Path(YOUTUBE_CLIENT_SECRETS)
    token_path = Path(YOUTUBE_TOKEN_FILE)

    if not secrets_path.exists():
        print(f"\n❌ Error: '{secrets_path}' not found!")
        print("Please place your downloaded 'client_secrets.json' in the 'secrets/' folder first.\n")
        return False

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("\n❌ Error: 'google-auth-oauthlib' is not installed.")
        print("Run: pip install google-api-python-client google-auth-oauthlib\n")
        return False

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
    print("\nStep 1: Copy and open this URL in ANY browser (on your PC, Mac, or phone):")
    print("-" * 70)
    print(auth_url)
    print("-" * 70)
    print("\nStep 2: Sign in with your YouTube account and grant permissions.")
    print("Step 3: After approval, your browser will try to load a page like:")
    print("        http://localhost:8080/?state=...&code=...")
    print("        (It might say 'Unable to connect' or 'Site can't be reached' — THAT IS NORMAL!)")
    print("\nStep 4: Copy the ENTIRE URL from your browser's address bar and paste it below:\n")

    redirect_response = input("Paste the full redirected URL here: ").strip()

    if not redirect_response:
        print("\n❌ No URL provided. Authentication aborted.")
        return False

    try:
        # In case user pasted with http:// replaced or whitespace
        if not redirect_response.startswith("http"):
            redirect_response = "http://" + redirect_response

        try:
            flow.fetch_token(authorization_response=redirect_response)
        except Exception as ex:
            if "insecure_transport" in str(ex).lower() and redirect_response.startswith("http://"):
                https_url = "https://" + redirect_response[7:]
                flow.fetch_token(authorization_response=https_url)
            else:
                raise
        creds = flow.credentials

        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

        print("\n" + "=" * 70)
        print("✅ SUCCESS! YouTube token generated and saved to:")
        print(f"   {token_path}")
        print("=" * 70)
        print("You can now run your uploads and daemon 24/7 without ever needing a browser!\n")
        return True

    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        print("Make sure you copied the complete redirect URL including the '?code=...' parameter.\n")
        return False


if __name__ == "__main__":
    authenticate_headless()
