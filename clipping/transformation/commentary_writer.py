"""
Generates original editorial and analytical commentary scripts using local Ollama.
This ensures the output qualifies as transformative fair-use analysis rather than raw reused content.
"""

import logging
import requests

from clipping.config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_AUTH_TOKEN, OLLAMA_TIMEOUT, NICHE_CONFIG
from clipping.models import ClipCandidate

logger = logging.getLogger("clipping.transformation.commentary_writer")


def write_commentary(clip: ClipCandidate) -> str:
    """
    Writes a 30-40 second spoken narration script providing original analysis of the clip.
    """
    prompt = f"""You are an elite business analyst and executive coach crafting a 35-second voiceover for a YouTube Short.

Clip context from {clip.source_channel}:
"{clip.transcript_segment[:400]}"

Narrator's analytical angle: {clip.commentary_angle or 'Explain the strategic leverage behind this idea'}

SCRIPT FORMAT & RULES:
1. HOOK (0-3s): Open with a pattern-interrupt sentence (under 10 words).
   Examples: "The biggest lie about building wealth is working harder." or "Here is why 90% of businesses fail to scale."
2. ANALYSIS (3-25s): Provide your ORIGINAL strategic breakdown. Do NOT just summarize the speaker.
   Add actionable business insights, counterpoints, or framework context.
   Keep sentences short, punchy, and conversational (max 10-12 words per sentence).
3. CTA (25-35s): Seamlessly wrap with a call to action: "Save this for your next project and follow for daily business breakdowns."

Target: 65 to 80 spoken English words (approx 30-35 seconds).
Return ONLY the clean spoken narration text without any labels, bullet points, or stage directions."""

    try:
        headers = {}
        if OLLAMA_AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {OLLAMA_AUTH_TOKEN}"

        logger.info(f"Generating transformative commentary via Ollama ({OLLAMA_MODEL})...")
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "top_p": 0.9},
            },
            headers=headers,
            timeout=OLLAMA_TIMEOUT,
        )
        if resp.status_code == 200:
            text = resp.json().get("response", "").strip()
            # Clean any artifacts or stage directions
            lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("[") and not l.startswith("Narrator:")]
            cleaned = " ".join(lines)
            if len(cleaned.split()) >= 30:
                logger.info(f"Generated commentary ({len(cleaned.split())} words).")
                return cleaned
    except Exception as e:
        logger.warning(f"Ollama failed for commentary ({e}). Utilizing high-converting structured fallback.")

    # High-converting fallback commentary
    fallback = (
        f"{clip.hook_sentence}. "
        f"Most entrepreneurs focus on working more hours, but true leverage comes from building systems that operate without you. "
        f"When you master capital allocation and high-value decision making, your revenue scales exponentially while your workload drops. "
        f"Save this insight and follow for daily high-performance business frameworks."
    )
    return fallback
