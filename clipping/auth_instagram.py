"""
Headless Meta / Instagram Graph API OAuth2 Authenticator.
Exchanges authorization code for long-lived Page Access Token and discovers
the connected Instagram Business Account ID automatically.
"""

import json
import logging
import os
import re
import sys
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

API_VERSION = "v19.0"
REDIRECT_URI = "http://localhost:8080/"


def authenticate_instagram():
    """
    Executes headless OAuth for Instagram Graph API:
    1. Prompts for Meta App ID & App Secret.
    2. Generates authorization URL with required scopes.
    3. User authorizes in any browser and pastes redirected URL.
    4. Exchanges code for short-lived token, then permanent Page Access Token.
    5. Discovers connected Instagram Business Account ID.
    6. Saves to secrets/instagram_token.json and updates .env.
    """
    print("\n" + "=" * 70)
    print("      HEADLESS INSTAGRAM GRAPH API OAUTH AUTHENTICATION")
    print("=" * 70)
    print("\nPrerequisites:")
    print("1. An Instagram Professional/Creator account connected to a Facebook Page.")
    print("2. A Meta App created on developers.facebook.com (type: 'Other' or 'Business')")
    print("   with 'Instagram Graph API' product added.")
    print("3. Valid OAuth Redirect URI set to: http://localhost:8080/\n")

    app_id = input("Enter your Meta App ID: ").strip()
    app_secret = input("Enter your Meta App Secret: ").strip()

    if not app_id or not app_secret:
        print("\n❌ App ID and App Secret are required. Aborting.")
        return False

    scopes = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"
    auth_url = (
        f"https://www.facebook.com/{API_VERSION}/dialog/oauth?"
        f"client_id={app_id}&redirect_uri={REDIRECT_URI}&scope={scopes}&response_type=code"
    )

    print("\nStep 1: Open this URL in ANY browser (on your PC, Mac, or phone):")
    print("-" * 70)
    print(auth_url)
    print("-" * 70)
    print("\nStep 2: Sign in with your Facebook account that manages your Instagram Page.")
    print("Step 3: After approval, your browser redirects to a page like:")
    print("        http://localhost:8080/?code=AQD...#_=_")
    print("        (It might say 'Unable to connect' — THAT IS NORMAL!)")
    print("\nStep 4: Copy the ENTIRE URL from your browser's address bar and paste it below:\n")

    redirect_response = input("Paste the redirected URL here: ").strip()
    if not redirect_response:
        print("\n❌ No URL provided. Aborting.")
        return False

    # Extract code parameter
    code = None
    if "code=" in redirect_response:
        code_part = redirect_response.split("code=")[1]
        code = code_part.split("&")[0].split("#")[0].strip()
    else:
        code = redirect_response.strip()

    print("\n[1/3] Exchanging authorization code for short-lived token...")
    token_url = f"https://graph.facebook.com/{API_VERSION}/oauth/access_token"
    res = requests.get(
        token_url,
        params={
            "client_id": app_id,
            "redirect_uri": REDIRECT_URI,
            "client_secret": app_secret,
            "code": code,
        },
        timeout=30,
    )
    data = res.json()
    short_token = data.get("access_token")

    if not short_token:
        print(f"\n❌ Failed to obtain token: {data}")
        return False

    print("[2/3] Exchanging for Long-Lived Access Token (permanent Page token)...")
    long_res = requests.get(
        token_url,
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    long_data = long_res.json()
    long_user_token = long_data.get("access_token", short_token)

    print("[3/3] Discovering connected Instagram Business Account ID...")
    accounts_res = requests.get(
        f"https://graph.facebook.com/{API_VERSION}/me/accounts",
        params={
            "fields": "name,access_token,instagram_business_account",
            "access_token": long_user_token,
        },
        timeout=30,
    )
    accounts_data = accounts_res.json()
    pages = accounts_data.get("data", [])

    if not pages:
        print("\n⚠️ No Facebook Pages found for this user account.")
        print("Please ensure your Instagram account is linked to a Facebook Page.")
        return False

    selected_page = None
    ig_account_id = None
    page_access_token = None

    for p in pages:
        ig_biz = p.get("instagram_business_account")
        if ig_biz:
            selected_page = p
            ig_account_id = ig_biz.get("id")
            page_access_token = p.get("access_token")
            break

    if not ig_account_id:
        print("\n⚠️ Facebook Page found, but no linked Instagram Business Account detected.")
        print("Open your Facebook Page Settings -> Linked Accounts -> Instagram, and connect your Instagram account.")
        return False

    print("\n" + "=" * 70)
    print("✅ INSTAGRAM AUTHENTICATION SUCCESSFUL!")
    print("=" * 70)
    print(f"Facebook Page: {selected_page.get('name')}")
    print(f"Instagram Account ID: {ig_account_id}")
    print(f"Permanent Page Token: {page_access_token[:25]}... (valid indefinitely)")
    print("=" * 70)

    # Save to secrets/instagram_token.json
    secrets_dir = PROJECT_ROOT / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    token_file = secrets_dir / "instagram_token.json"
    with open(token_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "instagram_account_id": ig_account_id,
                "access_token": page_access_token,
                "page_name": selected_page.get("name"),
            },
            f,
            indent=2,
        )
    print(f"\nToken saved to: {token_file}")

    # Automatically update or append to .env
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        if "INSTAGRAM_ACCESS_TOKEN=" in content:
            content = re.sub(r"INSTAGRAM_ACCESS_TOKEN=.*", f"INSTAGRAM_ACCESS_TOKEN={page_access_token}", content)
        else:
            content += f"\nINSTAGRAM_ACCESS_TOKEN={page_access_token}"

        if "INSTAGRAM_ACCOUNT_ID=" in content:
            content = re.sub(r"INSTAGRAM_ACCOUNT_ID=.*", f"INSTAGRAM_ACCOUNT_ID={ig_account_id}", content)
        else:
            content += f"\nINSTAGRAM_ACCOUNT_ID={ig_account_id}"

        env_file.write_text(content, encoding="utf-8")
        print(f"Updated {env_file} with your Instagram credentials!")

    print("\nInstagram Reels publishing is now 100% active!")
    return True


if __name__ == "__main__":
    authenticate_instagram()
