"""
Metadata Optimizer: Uses local Ollama or high-CTR templates to draft
Title A/B variants, SEO tags, and descriptions customized per profile.
"""

import json
import logging
from typing import Any, Dict, Optional
import requests

from clipping.config import (
    OLLAMA_URL,
    OLLAMA_MODEL,
    OLLAMA_AUTH_TOKEN,
    OLLAMA_TIMEOUT,
    NICHE_CONFIG,
)
from clipping.models import ClipCandidate
from clipping.profiles.base import ClipProfile
from clipping.profiles import DEFAULT_PROFILE
from clipping.publishing.affiliate_injector import inject_monetization_links

logger = logging.getLogger("clipping.publishing.metadata_optimizer")


def generate_metadata(
    clip: ClipCandidate,
    commentary: str,
    profile: Optional[ClipProfile] = None,
) -> Dict[str, Any]:
    """
    Generates A/B title variants, description, and pinned comment tuned for the active profile.
    """
    prof = profile or DEFAULT_PROFILE

    # Build profile-specific default titles
    if prof.name == "game-gta6":
        title_a = f"{clip.hook_sentence[:48]} 💀 #Shorts"
        title_b = f"GTA 6 Craziest Streamer Moment 😱 #Shorts"
    elif prof.name == "mrbeast":
        title_a = f"{clip.hook_sentence[:48]} 😱 #Shorts"
        title_b = f"He Actually Survived This Challenge 🤯 #Shorts"
    elif prof.name == "game-fortnite":
        title_a = f"{clip.hook_sentence[:48]} 🔥 #Shorts"
        title_b = f"Insane 200 IQ Fortnite Clutch 🏆 #Shorts"
    else:
        title_a = f"{clip.hook_sentence[:48]} 🤯 #Shorts"
        title_b = f"How To Win In {prof.display_name} 📈 #Shorts"

    prompt = f"""You are a master YouTube Shorts SEO algorithm editor for {prof.display_name}.
Given this clip highlight from {clip.source_channel}:
"{clip.hook_sentence}"
Transcript snippet: "{clip.transcript_segment[:200]}"

Generate 2 click-worthy, viral YouTube Shorts titles for A/B testing:
1. Title A: High curiosity/reaction, all caps or punchy (under 60 chars, 1 emoji, ends with #Shorts)
2. Title B: Action/question hook (under 60 chars, 1 emoji, ends with #Shorts)

Return ONLY valid JSON:
{{
  "title_a": "{title_a}",
  "title_b": "{title_b}"
}}"""

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
                "options": {"temperature": 0.5},
            },
            headers=headers,
            timeout=min(OLLAMA_TIMEOUT, 45),
        )
        if resp.status_code == 200:
            raw_text = resp.json().get("response", "").strip()
            data = json.loads(raw_text)
            if data.get("title_a") and len(data["title_a"].strip()) > 5:
                title_a = data["title_a"].strip()
            if data.get("title_b") and len(data["title_b"].strip()) > 5:
                title_b = data["title_b"].strip()
    except Exception as e:
        logger.debug(f"Ollama metadata generation skipped ({e}); using template titles.")

    # Guarantee #Shorts tag
    if "#shorts" not in title_a.lower():
        title_a = f"{title_a} #Shorts"
    if "#shorts" not in title_b.lower():
        title_b = f"{title_b} #Shorts"

    # Format description & pinned comment using profile templates if present
    summary_text = clip.hook_sentence
    if prof.description_template:
        description = prof.description_template.format(
            summary=summary_text,
            original_creator=clip.source_channel,
        )
        pinned_comment = prof.pinned_comment_template.format(
            original_creator=clip.source_channel,
        )
    else:
        links = inject_monetization_links(commentary, original_creator=clip.source_channel)
        description = links["description"]
        pinned_comment = links["pinned_comment"]

    return {
        "title_a": title_a,
        "title_b": title_b,
        "description": description,
        "pinned_comment": pinned_comment,
        "tags": prof.target_tags or NICHE_CONFIG.get("target_tags", ["Shorts", "Gaming"]),
        "category_id": prof.category_id or "20",
    }
