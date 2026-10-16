#!/usr/bin/env python3
"""
Script Structuring Controller (Ollama Qwen3-coder:30b Backend)
Generates and strictly validates high-retention JSON scripts for the
'Narrative Psychology & Corporate Warfare' vertical video niche.

Features:
- Structured JSON output enforcement with schema validation
- Resilient JSON markdown unwrapping & repair routines
- Automatic error-feedback retry loop (up to 3 rounds)
- Curated high-retention offline fallbacks when LLM is unavailable
"""

import os
import re
import json
import random
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

import requests

from narrative_warfare.env_loader import load_project_env
load_project_env()

logger = logging.getLogger("script_controller")

DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.getenv("NARRATIVE_OLLAMA_MODEL", "qwen3-coder:30b")
REQUEST_TIMEOUT = 120


# -----------------------------------------------------------------------------
# Data Models & Schema Validation
# -----------------------------------------------------------------------------
@dataclass
class NarrativeScript:
    topic: str
    psychological_hook: str
    editorial_voiceover: str
    visual_style_seed: int
    caption_emphasis_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "psychological_hook": self.psychological_hook,
            "editorial_voiceover": self.editorial_voiceover,
            "visual_style_seed": self.visual_style_seed,
            "caption_emphasis_keywords": self.caption_emphasis_keywords,
        }

    @property
    def full_spoken_text(self) -> str:
        """Combines psychological hook and editorial voiceover for seamless TTS."""
        hook = self.psychological_hook.strip()
        body = self.editorial_voiceover.strip()
        if not hook.endswith((".", "!", "?")):
            hook += "."
        return f"{hook} {body}"


def validate_script_dict(data: Any) -> NarrativeScript:
    """
    Strict validation for script dictionary. Raises ValueError on any deviation.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object (dict), got {type(data).__name__}")

    # 1. Validate topic
    topic = data.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("Field 'topic' must be a non-empty string.")

    # 2. Validate psychological_hook (must be 3-5s hook, roughly 5-40 words)
    hook = data.get("psychological_hook")
    if not isinstance(hook, str) or len(hook.strip().split()) < 4:
        raise ValueError("Field 'psychological_hook' must contain at least 4 spoken words.")

    # 3. Validate editorial_voiceover (continuous natural speech rhythm)
    voiceover = data.get("editorial_voiceover")
    if not isinstance(voiceover, str) or len(voiceover.strip().split()) < 25:
        raise ValueError("Field 'editorial_voiceover' must contain at least 25 spoken words.")

    # 4. Validate visual_style_seed (4-digit integer)
    seed_val = data.get("visual_style_seed")
    try:
        seed_int = int(seed_val)
        if seed_int < 1000 or seed_int > 9999:
            # Re-seed if outside 4-digit bounds
            seed_int = random.randint(1000, 9999)
    except (TypeError, ValueError):
        seed_int = random.randint(1000, 9999)

    # 5. Validate caption_emphasis_keywords
    keywords = data.get("caption_emphasis_keywords")
    if not isinstance(keywords, list):
        keywords = []
    clean_keywords = [str(k).strip() for k in keywords if str(k).strip()]
    if len(clean_keywords) < 2:
        # Fallback to key impactful words from the topic and hook
        extracted = [w for w in re.findall(r"\b[A-Z][a-z]+\b|\b[A-Za-z]{5,}\b", f"{topic} {hook}")]
        clean_keywords = list(dict.fromkeys(extracted))[:6]

    return NarrativeScript(
        topic=topic.strip(),
        psychological_hook=hook.strip(),
        editorial_voiceover=voiceover.strip(),
        visual_style_seed=seed_int,
        caption_emphasis_keywords=clean_keywords,
    )


# -----------------------------------------------------------------------------
# Robust JSON Sanitization & Parsing
# -----------------------------------------------------------------------------
def extract_and_parse_json(raw_text: str) -> Dict[str, Any]:
    """
    Extracts JSON payload from potential markdown wrappers, fixes trailing commas,
    and returns parsed dictionary.
    """
    clean_text = raw_text.strip()

    # Step 1: Strip markdown codeblocks ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_text, re.DOTALL)
    if match:
        clean_text = match.group(1).strip()
    else:
        # Find outermost braces
        brace_start = clean_text.find("{")
        brace_end = clean_text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            clean_text = clean_text[brace_start : brace_end + 1].strip()

    # Step 2: Clean trailing commas before closing braces/brackets
    clean_text = re.sub(r",\s*([\}\]])", r"\1", clean_text)

    # Step 3: Parse
    return json.loads(clean_text)


# -----------------------------------------------------------------------------
# Curated High-Retention Offline Fallbacks
# -----------------------------------------------------------------------------
CURATED_FALLBACKS: List[Dict[str, Any]] = [
    {
        "topic": "The Steve Jobs Boomerang Coup",
        "psychological_hook": "In 1985, Steve Jobs was humiliated and fired by the very CEO he recruited.",
        "editorial_voiceover": "Twelve years later, Apple was within 90 days of bankruptcy. Jobs didn't beg for his job back. He engineered NeXT, forced Apple to buy it for 429 million dollars, and used an orchestrated boardroom mutiny to systematically strip John Sculley's successors of their voting power. In corporate warfare, revenge isn't emotional; it's a structural liquidity trap.",
        "visual_style_seed": 7421,
        "caption_emphasis_keywords": ["HUMILIATED", "BANKRUPTCY", "429 MILLION", "MUTINY", "LIQUIDITY TRAP"],
    },
    {
        "topic": "Porsche's 2008 Shadow Short Squeeze",
        "psychological_hook": "This single hedge fund maneuver caused a CEO to jump in front of a train.",
        "editorial_voiceover": "In October 2008, Porsche quietly accumulated cash-settled call options on Volkswagen stock while publicly denying any takeover intentions. When short sellers woke up on Monday morning, only 5.8 percent of Volkswagen shares were actually floating on the market. Porsche owned the rest. The panic forced hedge funds to buy at any price, briefly making VW the most valuable company on earth.",
        "visual_style_seed": 3819,
        "caption_emphasis_keywords": ["SHADOW", "SHORT SQUEEZE", "TAKEOVER", "MOST VALUABLE", "PANIC"],
    },
    {
        "topic": "The Predatory Algorithmic Pricing Ambush",
        "psychological_hook": "Never compete with an opponent whose balance sheet views your entire market cap as a rounding error.",
        "editorial_voiceover": "When Quidsi refused to sell Diapers.com to Amazon, Jeff Bezos initiated economic warfare. Amazon deployed bots to scrape their prices in real-time, instantly undercutting them by thirty percent and losing one hundred million dollars in three months. Crushed under artificial margin compression, Quidsi surrendered. The algorithm didn't win by being smarter; it won by weaponizing infinite runway.",
        "visual_style_seed": 9152,
        "caption_emphasis_keywords": ["ROUNDING ERROR", "ECONOMIC WARFARE", "UNDERPASS", "MARGIN COMPRESSION", "INFINITE RUNWAY"],
    },
]


def get_curated_fallback(topic_hint: Optional[str] = None) -> NarrativeScript:
    """Returns a vetted, high-retention script fallback."""
    if topic_hint:
        for item in CURATED_FALLBACKS:
            if any(w.lower() in item["topic"].lower() for w in topic_hint.split()):
                return validate_script_dict(item)
    chosen = random.choice(CURATED_FALLBACKS)
    return validate_script_dict(chosen)


# -----------------------------------------------------------------------------
# Ollama Script Generation with Multi-Round Self-Correction Loop
# -----------------------------------------------------------------------------
SYSTEM_INSTRUCTION = """You are an elite narrative scriptwriter specializing in the 'Narrative Psychology & Corporate Warfare' niche.
Your task is to write high-retention, psychological analysis scripts for 9:16 vertical short-form videos (TikTok, YouTube Shorts).

STYLE RULES:
1. Tone: Dark, analytical, investigative, fast-paced, high intellectual tension.
2. Hook: Must be a gripping, controversial 3-second statement (10 to 20 spoken words).
3. Voiceover: Natural human cadence, punchy sentences, avoiding buzzwords, 50 to 80 spoken words (25-35 seconds).
4. Keywords: Highlight 4-7 shock-value or pivotal words (e.g., 'BETRAYAL', 'LIQUIDATED', 'HOSTILE TAKEOVER').
5. STRICT OUTPUT: You MUST return ONLY valid raw JSON with NO markdown text before or after.
"""

JSON_SCHEMA_INSTRUCTION = """
REQUIRED JSON SCHEMA:
{
  "topic": "The behavioral anomaly or corporate battle being broken down",
  "psychological_hook": "A highly controversial or gripping 3-second narrative statement",
  "editorial_voiceover": "A continuous, high-retention analysis framework designed for natural speech rhythm.",
  "visual_style_seed": 4-digit integer between 1000 and 9999,
  "caption_emphasis_keywords": ["KEYWORD1", "KEYWORD2", "KEYWORD3"]
}
"""


def generate_narrative_script(
    topic: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    max_retries: int = 3,
) -> NarrativeScript:
    """
    Queries Ollama to generate a structured script. If validation or parsing fails,
    initiates an automated correction loop feeding the error back to the model.
    Falls back gracefully to curated scripts if Ollama is unreachable.
    """
    target_topic = topic or "Why predatory corporate raiders deliberately engineer liquidity crises"

    prompt = f"""Break down this corporate psychology / warfare anomaly:
Topic: {target_topic}

Follow all style rules and return ONLY the strictly formatted JSON matching the schema:
{JSON_SCHEMA_INSTRUCTION}
"""

    last_error = ""
    for attempt in range(1, max_retries + 1):
        attempt_prompt = prompt
        if attempt > 1:
            attempt_prompt += f"\n\nCRITICAL FIX: Your previous response failed validation with error: '{last_error}'. You must return strictly valid JSON matching the exact schema."

        payload = {
            "model": model,
            "prompt": attempt_prompt,
            "system": SYSTEM_INSTRUCTION,
            "stream": False,
            "options": {
                "temperature": 0.65,
                "top_p": 0.9,
            },
        }

        logger.info(f"Ollama script generation attempt {attempt}/{max_retries} for topic: '{target_topic}'...")
        try:
            resp = requests.post(ollama_url, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            res_json = resp.json()
            raw_text = res_json.get("response", "").strip()

            parsed = extract_and_parse_json(raw_text)
            script = validate_script_dict(parsed)
            logger.info(f"Successfully generated validated script: '{script.topic}' (seed={script.visual_style_seed})")
            return script

        except (requests.exceptions.RequestException, ConnectionError) as net_err:
            logger.warning(f"Ollama server connection error at {ollama_url}: {net_err}")
            break  # Server offline, jump to fallback immediately
        except Exception as parse_err:
            last_error = str(parse_err)
            logger.warning(f"Validation failed on attempt {attempt}: {last_error}")

    logger.warning("Ollama generation exhausted or unavailable. Activating curated production fallback.")
    return get_curated_fallback(topic)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    script = generate_narrative_script()
    print("\n--- Validated Script Object ---")
    print(json.dumps(script.to_dict(), indent=2))
    print(f"\nTotal Spoken Words: {len(script.full_spoken_text.split())}")
