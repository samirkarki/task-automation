#!/usr/bin/env python3
"""
Faceless Content Generator, Video Auto-Renderer & Social Publisher
Queries local Ollama (qwen3-coder:30b) to draft viral 30-second short-form financial scripts,
synthesizes neural TTS audio, renders an animated 9:16 vertical MP4 video via MoviePy,
publishes directly to YouTube Shorts (with Telegram CTA & Affiliate links),
syncs assets to Google Drive via rclone, and automatically purges local staging files.
"""

import os
import re
import sys
import json
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests

from faceless_content.tts_engine import synthesize_speech, split_text_into_subtitles
from faceless_content.video_renderer import render_short_video
from faceless_content.youtube_publisher import publish_short_video

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")
REQUEST_TIMEOUT = 300
DEFAULT_RCLONE_REMOTE = os.getenv("RCLONE_CONTENT_REMOTE", "gdrive:FacelessContent/")

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("content_generator")


# -----------------------------------------------------------------------------
# Ollama Interaction
# -----------------------------------------------------------------------------
def query_ollama(
    prompt: str,
    system_instruction: str,
    model: str = DEFAULT_MODEL,
    url: str = OLLAMA_URL,
    timeout: int = REQUEST_TIMEOUT,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_instruction,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
        },
    }

    logger.info(f"Querying Ollama at {url} using model '{model}' (timeout={timeout}s)...")
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        generated_text = result.get("response", "").strip()

        if not generated_text:
            raise ValueError("Ollama returned an empty response.")

        logger.info(f"Generated script ({len(generated_text)} characters).")
        return generated_text

    except requests.exceptions.Timeout:
        logger.error(f"Ollama request timed out after {timeout} seconds.")
        raise
    except requests.exceptions.ConnectionError as ce:
        logger.error(f"Cannot reach Ollama at {url}. Error: {ce}")
        raise
    except Exception as ex:
        logger.error(f"Error querying Ollama: {ex}")
        raise


def build_script_prompt(topic: Optional[str] = None, market_context: Optional[str] = None) -> str:
    active_topic = topic or "Why 90% of NEPSE retail traders buy at the 2800 top and panic sell at the bottom"
    context_str = market_context or "Recent NEPSE turnover surge, sector rotation into Hydropower and Non-Life Insurance, key resistance at 2800."

    prompt = f"""
Write a high-retention, viral 30-second short-form video script (YouTube Shorts, TikTok, Instagram Reels) for a faceless financial intelligence channel focusing on the Nepal Stock Exchange (NEPSE).

Topic: {active_topic}
Market Context: {context_str}

CRITICAL DUAL-LANGUAGE REQUIREMENT:
1. Spoken Voiceover MUST be in natural, conversational NEPALI language (Devanagari script).
   - Tone: Energetic, authoritative, human, like an experienced Kathmandu financial analyst and trader.
   - Pacing: Strictly 65 to 80 spoken Nepali words (28-32 seconds of clear, natural conversational cadence).
   - Seamlessly integrate standard market terms (NEPSE, Stop Loss, RSI, Breakout, Broker, Target, Support, Resistance).
2. On-screen Subtitles/Captions MUST be in punchy, high-impact ENGLISH (all caps, 3-5 words each).
   - Viewers will LISTEN to human Nepali voiceover while READING dynamic English captions on screen!

Structure the script into these explicit sections:

1. [HOOK] (00:00 - 00:03)
   - Visual: Aggressive zoom-in on red chart candles or index high.
   - Voiceover (Nepali): [१ वाक्यको शक्तिशाली नेपाली हुक - जस्तै: "नेप्से २८०० पुग्दा फेरि साना लगानीकर्ता फस्ने निश्चित भयो?"]
   - English Caption: [PUNCHY 3-5 WORD ENGLISH HOOK]

2. [PROBLEM & TRAP] (00:03 - 00:12)
   - Visual: Fast panic selling b-roll, falling candles.
   - Voiceover (Nepali): [२ वाक्यको समस्या र रिटेल ट्रयाप - जस्तै: "जब बजार टपमा पुग्छ, सामाजिक सञ्जालमा हल्ला चल्छ र रिटेल ट्रेडरहरू एफओएमओमा सेयर किन्छन्। तर स्मार्ट मनि यहाँ सेयर डम्प गरिरहेका छन्।"]
   - English Caption: [2 SHORT PUNCHY ENGLISH CAPTION LINES]

3. [SMART MONEY INSIGHT] (00:12 - 00:23)
   - Visual: Broker accumulation floorsheet, RSI divergence, green support line.
   - Voiceover (Nepali): [२ वाक्यको संस्थागत रणनीति - जस्तै: "ठूला ब्रोकरहरूको एक्युमुलेसन हेर्नुहोस्। जबसम्म ब्रेकआउट भोल्युमले पुष्टि गर्दैन, नयाँ खरिद नगर्नुहोस् र स्टप लस कडाइका साथ राख्नुहोस्।"]
   - English Caption: [2 SHORT PUNCHY ENGLISH CAPTION LINES]

4. [CALL TO ACTION & OUTRO] (00:23 - 00:30)
   - Visual: Telegram VIP signal card and follow animation.
   - Voiceover (Nepali): [१ वाक्यको निष्कर्ष र फलो गर्न आह्वान - जस्तै: "दैनिक नेप्से इन्टेलिजेन्स र हाई-विनरेट सिग्नलको लागि अहिले नै फलो र सेभ गर्नुहोस्।"]
   - English Caption: [ENGLISH CALL TO ACTION CAPTION]

5. [PRODUCTION ASSETS & B-ROLL MANIFEST]
   - List 4 B-roll keywords.
   - Music vibe suggestion: Ambient cinematic suspense with modern pulse.
"""
    return prompt.strip()


def build_system_instruction() -> str:
    return (
        "You are an award-winning bilingual financial video director and NEPSE market analyst. "
        "You craft viral short-form scripts where the spoken voiceover is authentic, conversational, "
        "human-sounding Nepali (in Devanagari script), while the on-screen video captions are punchy, "
        "high-impact English (3-5 words per line) for maximum engagement on TikTok and YouTube Shorts."
    )


def extract_voiceover_and_captions(script_text: str) -> Tuple[str, List[str]]:
    """
    Extracts:
    1. nepali_voiceover: Spoken Nepali script in Devanagari for natural neural TTS.
    2. english_captions: List of English subtitle cards for on-screen video overlay.
    """
    nepali_lines = []
    english_caption_lines = []

    for line in script_text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue

        # Extract Voiceover lines (Nepali)
        vo_match = re.search(
            r"(?:Voiceover\s*(?:\(Nepali\)|\(ne\)|\bNepali\b)?|Nepali Voiceover|Voice-over):\s*(.+)",
            line_clean,
            re.IGNORECASE,
        )
        if vo_match:
            text_cand = vo_match.group(1).strip().strip('"').strip("'")
            text_cand = re.sub(r"\[.*?\]", "", text_cand).strip()
            if text_cand:
                nepali_lines.append(text_cand)
            continue

        # Extract English Captions / Subtitles
        cap_match = re.search(
            r"(?:English Caption|English Captions|Caption|Text Overlay|On-screen Text):\s*(.+)",
            line_clean,
            re.IGNORECASE,
        )
        if cap_match:
            cap_cand = cap_match.group(1).strip().strip('"').strip("'")
            cap_cand = re.sub(r"\[.*?\]", "", cap_cand).strip()
            if cap_cand and not re.search(r"[\u0900-\u097F]", cap_cand):
                english_caption_lines.append(cap_cand.upper())
            continue

    # Devanagari fallback extraction if no explicit Voiceover tag matched
    if not nepali_lines:
        for line in script_text.splitlines():
            if any(tag in line.lower() for tag in ["visual:", "manifest", "http", "#", "production", "topic:"]):
                continue
            if re.search(r"[\u0900-\u097F]", line):
                clean_dev = re.sub(r"^[0-9\.\-\*\#\s]+", "", line).strip().strip('"')
                clean_dev = re.sub(r"\[.*?\]", "", clean_dev).strip()
                if len(clean_dev) > 10:
                    nepali_lines.append(clean_dev)

    # Fallback default Nepali voiceover if empty
    if not nepali_lines:
        nepali_lines = [
            "नेप्से परिसूचक २८०० को महत्त्वपूर्ण प्रतिरोध विन्दुमा पुगेको छ।",
            "ठूला खेलाडी र स्मार्ट मनि आफ्नो नाफा सुरक्षित गर्दैछन्, तर साना लगानीकर्ताहरू भने एफओएमओमा फसेर टपमा सेयर किन्दैछन्।",
            "यदि तपाईं बजारमा सुरक्षित नाफा कमाउन चाहनुहुन्छ भने स्टप लस कडाइका साथ पालना गर्नुहोस् र संस्थागत संकलन भएका स्क्रिप्टहरूमा मात्र ध्यान दिनुहोस्।",
            "दैनिक नेप्से इन्टेलिजेन्सको लागि हाम्रो टेलिग्राम च्यानलमा जोडिनुहोस्।",
        ]

    # Fallback English captions if empty
    if not english_caption_lines:
        english_caption_lines = [
            "NEPSE MARKET WARNING",
            "RETAIL TRADERS TRAPPED AT 2800",
            "SMART MONEY IS DUMPING",
            "TRACK INSTITUTIONAL FLOWS",
            "SET YOUR STRICT STOPLOSS",
            "FOLLOW FOR VIP SIGNALS",
        ]

    voiceover_text = " ".join(nepali_lines)
    return voiceover_text, english_caption_lines


def extract_voiceover_lines(script_text: str) -> str:
    """Backward-compatible helper returning the spoken voiceover string."""
    vo, _ = extract_voiceover_and_captions(script_text)
    return vo


# -----------------------------------------------------------------------------
# File Staging & Rclone Synchronization
# -----------------------------------------------------------------------------
def sync_assets_to_remote(staged_files: List[Path], remote_destination: str = DEFAULT_RCLONE_REMOTE) -> bool:
    logger.info(f"Syncing {len(staged_files)} file(s) to '{remote_destination}'...")
    for file_path in staged_files:
        if not file_path.exists():
            continue
        cmd = ["rclone", "copy", str(file_path), remote_destination]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            file_path.unlink()
            logger.info(f"Uploaded and cleaned up staging file: {file_path.name}")
        except Exception as e:
            logger.error(f"Failed to sync {file_path.name}: {e}")
            raise
    return True


# -----------------------------------------------------------------------------
# Main Video Generation Pipeline
# -----------------------------------------------------------------------------
def run_generator(
    topic: Optional[str] = None,
    context: Optional[str] = None,
    remote_dest: str = DEFAULT_RCLONE_REMOTE,
    model: str = DEFAULT_MODEL,
    skip_rclone: bool = False,
    skip_video: bool = False,
    skip_youtube: bool = False,
) -> Tuple[Path, Optional[Path]]:
    """
    1. Query Ollama for viral script
    2. Synthesize speech (Edge-TTS)
    3. Render 9:16 vertical video (MoviePy + Pillow)
    4. Auto-publish to YouTube Shorts with Telegram CTA & affiliate links
    5. Sync backup to Google Drive & purge local staging files
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    active_topic = topic or "Why 90% of NEPSE retail traders buy at the top"

    # 1. Query Ollama
    prompt = build_script_prompt(active_topic, context)
    system_instruction = build_system_instruction()
    script_text = query_ollama(prompt, system_instruction, model=model)

    script_path = OUTPUT_DIR / f"faceless_script_{timestamp_str}.md"
    manifest_path = OUTPUT_DIR / f"faceless_manifest_{timestamp_str}.json"

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_text)

    manifest_data = {
        "timestamp": datetime.now().isoformat(),
        "topic": active_topic,
        "target_duration_seconds": 30,
        "format": "9:16_vertical_short",
        "resolution": "1080x1920",
        "fps": 24,
    }

    staged_items = [script_path]
    video_path = None

    # 2. Speech & Video Render
    if not skip_video:
        try:
            voiceover_text, english_captions = extract_voiceover_and_captions(script_text)
            logger.info(f"Extracted Nepali Voiceover: \"{voiceover_text[:90]}...\"")
            logger.info(f"Extracted {len(english_captions)} English caption card(s) for on-screen subtitles.")

            audio_path = OUTPUT_DIR / f"voiceover_{timestamp_str}.mp3"
            synthesize_speech(voiceover_text, audio_path)

            try:
                from faceless_content.moviepy_compat import AudioFileClip
                if AudioFileClip is not None:
                    a_clip = AudioFileClip(str(audio_path))
                    dur = a_clip.duration
                    a_clip.close()
                else:
                    dur = 28.0
            except Exception:
                dur = 28.0

            # On-screen subtitles rendered in English while voiceover speaks human Nepali
            subtitles = split_text_into_subtitles(english_captions, total_duration=dur)

            # Render 9:16 MP4 Video
            video_path = OUTPUT_DIR / f"faceless_video_{timestamp_str}.mp4"
            render_short_video(audio_path, subtitles, video_path, topic=active_topic)

            staged_items.append(audio_path)
            manifest_data["video_file"] = video_path.name
            manifest_data["audio_file"] = audio_path.name

            # 3. Auto-Publish to YouTube Shorts
            if not skip_youtube:
                logger.info("Auto-publishing video to YouTube Shorts...")
                yt_url = publish_short_video(video_path, topic=active_topic)
                if yt_url:
                    manifest_data["youtube_url"] = yt_url

            staged_items.append(video_path)
            manifest_data["video_status"] = "RENDERED_SUCCESSFULLY"

        except Exception as ve:
            logger.error(f"[VIDEO RENDER ERROR] Failed to render short video: {ve}", exc_info=True)
            logger.error(
                "[TROUBLESHOOTING] Please verify on the YetiCloud server:\n"
                "1. ffmpeg is installed: run 'sudo apt install -y ffmpeg'\n"
                "2. Virtual environment has dependencies: run 'pip install -r requirements.txt'\n"
                "3. Fonts are installed: run 'sudo apt install -y fonts-dejavu-core'"
            )
            manifest_data["video_status"] = "FAILED"
            manifest_data["video_error"] = str(ve)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    staged_items.append(manifest_path)

    # 4. Sync & Clean
    if not skip_rclone:
        sync_assets_to_remote(staged_items, remote_destination=remote_dest)
    else:
        logger.info(f"[DRY-RUN/SKIP] Skipping rclone sync. Files saved in {OUTPUT_DIR}")

    return script_path, video_path


def main():
    parser = argparse.ArgumentParser(description="Faceless Content Generator & Social Auto-Publisher")
    parser.add_argument("--topic", type=str, default=None)
    parser.add_argument("--context", type=str, default=None)
    parser.add_argument("--remote", type=str, default=DEFAULT_RCLONE_REMOTE)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--skip-video", action="store_true")
    parser.add_argument("--skip-youtube", action="store_true")
    parser.add_argument("--skip-rclone", action="store_true")

    args = parser.parse_args()

    try:
        run_generator(
            topic=args.topic,
            context=args.context,
            remote_dest=args.remote,
            model=args.model,
            skip_rclone=args.skip_rclone,
            skip_video=args.skip_video,
            skip_youtube=args.skip_youtube,
        )
        logger.info("Faceless Content Generator workflow completed successfully.")
    except Exception as exc:
        logger.critical(f"Content generator failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
