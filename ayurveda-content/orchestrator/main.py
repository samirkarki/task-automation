#!/usr/bin/env python3
"""
Ayurveda Content Automation Orchestrator
Uses common shared libraries for:
- Environment management (.env)
- LLM generation (Ollama)
- Neural Audio TTS (Kokoro)
- Word-level Subtitle Timestamps (Whisper)
- Stock Video Footage (Pexels)
- Multi-Platform Publishing (YouTube, Instagram, TikTok)
"""

import json
import os
import sys
from pathlib import Path

# Add project root to sys.path so common package is always discoverable
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output on Windows terminals for Unicode/Hindi characters
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from common.env_loader import load_project_env
load_project_env()

from common.ollama_client import query_ollama_json
from common.tts_engine import synthesize_with_kokoro
from common.whisper_utils import transcribe_audio_words
from common.stock_media import download_batch_stock_videos


def load_system_prompt() -> str:
    """Load system instructions from PROMPT.md (or PROMPT.txt if not found)."""
    current_dir = Path(__file__).resolve().parent
    candidates = [
        current_dir.parent / "PROMPT.md",
        current_dir.parent / "PROMPT.txt",
        current_dir / "PROMPT.md",
        current_dir / "PROMPT.txt",
    ]

    for candidate in candidates:
        if candidate.is_file():
            print(f"[+] Loaded instructions from: {candidate.name}")
            return candidate.read_text(encoding="utf-8").strip()

    raise FileNotFoundError(
        f"Could not find PROMPT.md or PROMPT.txt in {[str(c) for c in candidates]}"
    )


def get_mock_script() -> dict:
    """Fallback sample script used when Ollama is offline."""
    return {
        "topic": "Benefits of Ashwagandha for stress relief",
        "visual_search_queries": [
            "ashwagandha roots herbs",
            "calm peaceful nature meditation",
            "warm herbal tea pouring",
        ],
        "english_script": {
            "hook": "Constantly stressed and exhausted? Ayurveda holds the ancient secret to modern calm.",
            "body": "Meet Ashwagandha, the king of adaptogenic herbs. It regulates cortisol levels, naturally easing anxiety while revitalizing your energy without midday jitters. Take it with warm milk before sleep.",
            "cta": "Subscribe for daily Ayurvedic remedies to balance your Doshas!",
        },
        "hindi_script": {
            "hook": "क्या आप तनाव और थकान से परेशान हैं? आयुर्वेद में छिपा है शांति का राज़।",
            "body": "अश्वगंधा कोर्टिसोल को नियंत्रित करके तनाव को शांत करता है और ऊर्जा बढ़ाता है। इसे रात को गुनगुने दूध के साथ लें।",
            "cta": "दोषों को संतुलित करने और अधिक आयुर्वेदिक सुझावों के लिए सब्सक्राइब करें!",
        },
    }


def generate_ayurveda_script(topic: str) -> dict:
    """Generate structured JSON script using common Ollama client."""
    system_prompt = load_system_prompt()
    prompt = f"Generate a video script for the following Ayurvedic topic:\n\nTopic: {topic}"
    return query_ollama_json(prompt=prompt, system=system_prompt)


def main():
    test_topic = "Benefits of Ashwagandha for stress relief"
    current_dir = Path(__file__).resolve().parent

    print(f"=== Ayurveda Video Generation Pipeline ===")
    print(f"Topic: '{test_topic}'\n")

    # 1. Obtain script from Ollama (or fallback to mock if Ollama server is offline)
    try:
        script_json = generate_ayurveda_script(test_topic)
    except Exception as e:
        print(f"[*] Ollama server unavailable ({e}). Using sample script to test audio pipeline...")
        script_json = get_mock_script()

    print("\n=== Script Details ===")
    print(json.dumps(script_json, indent=2, ensure_ascii=False))

    # 2. Combine hook, body, and cta from English script
    english_data = script_json.get("english_script", {})
    hook = english_data.get("hook", "").strip()
    body = english_data.get("body", "").strip()
    cta = english_data.get("cta", "").strip()

    combined_text = f"{hook} {body} {cta}".strip()
    print(f"\n[*] Combined Script for TTS ({len(combined_text.split())} words):")
    print(f"    \"{combined_text}\"\n")

    # 3. Generate Audio via Kokoro TTS (using common.tts_engine)
    audio_output = current_dir / "audio.wav"
    synthesize_with_kokoro(
        text=combined_text,
        output_path=audio_output,
        voice="af_heart",
        lang_code="a",
    )

    # 4. Generate Word-Level Timestamps via OpenAI Whisper (using common.whisper_utils)
    subtitles_output = current_dir / "subtitles.json"
    transcribe_audio_words(
        audio_path=audio_output,
        output_json_path=subtitles_output,
    )

    # 5. Download Stock Videos via Pexels (using common.stock_media)
    search_queries = script_json.get("visual_search_queries", [])
    if search_queries:
        print(f"\n[*] Fetching stock footage for queries: {search_queries}")
        stock_dir = current_dir / "assets" / "clips"
        downloaded_clips = download_batch_stock_videos(search_queries, output_dir=stock_dir)
        print(f"[+] Downloaded {len(downloaded_clips)} stock clips to: {stock_dir}")

    print(f"\n[OK] Pipeline completed successfully!")
    print(f"   Audio:     {audio_output}")
    print(f"   Subtitles: {subtitles_output}")


if __name__ == "__main__":
    main()
