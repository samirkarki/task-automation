"""
Metadata Optimizer: Uses local Ollama to draft high-CTR Title A/B variants,
SEO tags, and monetization-packed descriptions.
"""

import json
import logging
import re
from typing import Dict, Any
import requests

from clipping.config import (
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_AUTH_TOKEN,
    OLLAMA_TIMEOUT,
    NICHE_CONFIG,
)
from clipping.models import ClipCandidate
from clipping.publishing.affiliate_injector import inject_monetization_links

logger = logging.getLogger("clipping.publishing.metadata_optimizer")


def generate_metadata(clip: ClipCandidate, commentary: str) -> Dict[str, Any]:
    """
    Generates A/B title variants, description with day-1 affiliate links, and pinned comment.
    """
    prompt = f"""You are a YouTube Shorts SEO algorithm specialist for {NICHE_CONFIG['name']}.
Given this video commentary, generate 2 click-worthy titles for A/B testing.

Commentary summary:
"{commentary[:300]}"

RULES:
1. Title A (CURIOSITY GAP): Starts with 'This...', 'Why...', or 'The secret...'
2. Title B (DIRECT VALUE): Starts with 'How to...', '3 Rules...', or 'The #1 way...'
3. Length: Strictly under 65 characters each.
4. Include 1 relevant emoji and end with '#Shorts'.
5. Must accurately reflect the content (high CTR without bait-and-switch).

Return ONLY valid JSON:
{{
  "title_a": "Why Working Harder Keeps You Broke 🤯 #Shorts",
  "title_b": "How To Build Wealth With Real Leverage 📈 #Shorts"
}}"""

    title_a = f"{clip.hook_sentence[:50]} 🤯 #Shorts"
    title_b = f"How To Win In Business & Wealth 📈 #Shorts"

    try:
        headers = {}
        if OLLAMA_AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {OLLAMA_AUTH_TOKEN}"

        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.7},
            },
            headers=headers,
            timeout=OLLAMA_TIMEOUT,
        )
        if resp.status_code == 200:
            raw_text = resp.json().get("response", "").strip()
            data = json.loads(raw_text)
            if data.get("title_a"):
                title_a = data["title_a"].strip()
            if data.get("title_b"):
                title_b = data["title_b"].strip()
    except Exception as e:
        logger.warning(f"Ollama title generation fallback ({e}). Using default templates.")

    # Ensure titles end with #Shorts
    if "#shorts" not in title_a.lower():
        title_a = f"{title_a} #Shorts"
    if "#shorts" not in title_b.lower():
        title_b = f"{title_b} #Shorts"

    links = inject_monetization_links(commentary, original_creator=clip.source_channel)

    return {
        "title_a": title_a,
        "title_b": title_b,
        "description": links["description"],
        "pinned_comment": links["pinned_comment"],
        "tags": NICHE_CONFIG.get("target_tags", ["Shorts", "Business", "Wealth"]),
        "category_id": NICHE_CONFIG.get("category_id", "22"),
    }
