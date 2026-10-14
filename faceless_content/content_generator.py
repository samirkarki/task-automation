#!/usr/bin/env python3
"""
Faceless Content Generator & Video Auto-Renderer
Queries local Ollama (qwen3-coder:30b) to draft viral 30-second short-form financial scripts,
synthesizes neural TTS audio, renders an animated 9:16 vertical MP4 video via MoviePy,
syncs assets directly to Google Drive via rclone, and automatically purges local staging files.
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

import requests

from faceless_content.tts_engine import synthesize_speech, split_text_into_subtitles
from faceless_content.video_renderer import render_short_video

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")
REQUEST_TIMEOUT = 300  # 300-second robust timeout
DEFAULT_RCLONE_REMOTE = os.getenv("RCLONE_CONTENT_REMOTE", "gdrive:FacelessContent/")

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

# -----------------------------------------------------------------------------
# Logging Setup
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
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
    """
    Sends a script generation request to the local Ollama instance with a 300s timeout.
    """
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

        logger.info(f"Successfully generated script ({len(generated_text)} characters).")
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


# -----------------------------------------------------------------------------
# Prompt Engineering & Extraction
# -----------------------------------------------------------------------------
def build_script_prompt(topic: Optional[str] = None, market_context: Optional[str] = None) -> str:
    active_topic = topic or "Why 90% of NEPSE retail traders buy at the top and panic sell at the bottom"
    context_str = market_context or "Recent NEPSE turnover surge, sector rotation into Hydropower and Non-Life Insurance, key resistance at 2800."

    prompt = f"""
Write a high-retention, viral 30-second short-form video script (TikTok, YouTube Shorts, Instagram Reels) for a faceless financial channel focusing on the Nepal Stock Exchange (NEPSE).

Topic: {active_topic}
Market Context: {context_str}

Format Requirements:
- Exact Pacing: Total spoken words must be strictly between 65 to 80 words (approximately 28-32 seconds of rapid, clear speech).
- Language: English (accessible, high-energy financial terminology).
- Tone: Punchy, urgent, high-status, psychological, no fluff.

Structure the script into these explicit sections:

1. [HOOK] (00:00 - 00:03)
   - Visual: Aggressive zoom-in or striking visual text.
   - Voiceover: [Write the exact 1-sentence hook here]
   - Text Overlay: Bold 3-4 word curiosity trap.

2. [PROBLEM & TRAP] (00:03 - 00:12)
   - Visual: Fast b-roll cues (red candles, panic selling).
   - Voiceover: [Write the exact 2-sentence problem here]
   - Text Overlay: Key emotional triggers.

3. [THE INSIDER INSIGHT] (00:12 - 00:23)
   - Visual: Green breakout charts, volume indicator spikes.
   - Voiceover: [Write the exact 2-sentence insight here]
   - Text Overlay: The actionable rule.

4. [CALL TO ACTION & OUTRO] (00:23 - 00:30)
   - Visual: Follow animation / comment trigger.
   - Voiceover: [Write the exact outro and question here]
   - Text Overlay: "Save this before your next trade."

5. [PRODUCTION ASSETS & B-ROLL MANIFEST]
   - List 4 royalty-free B-roll keywords.
   - Music vibe suggestion.
"""
    return prompt.strip()


def build_system_instruction() -> str:
    return (
        "You are an award-winning short-form video director and viral financial scriptwriter. "
        "You master 30-second hooks, dopamine-driven storytelling, viewer retention curves, "
        "and clean visual cue prompts for faceless video automation channels."
    )


def extract_voiceover_lines(script_text: str) -> str:
    """
    Parses the script output to extract the spoken voiceover dialogue for TTS synthesis.
    """
    voiceover_lines = []
    for line in script_text.splitlines():
        # Match lines like "Voiceover: ..." or "- Voiceover: ..."
        match = re.search(r"Voiceover:\s*(.+)", line, re.IGNORECASE)
        if match:
            clean_text = match.group(1).strip().strip('"').strip("'")
            # Strip bracketed remarks like [Aggressive tone]
            clean_text = re.sub(r"\[.*?\]", "", clean_text).strip()
            if clean_text:
                voiceover_lines.append(clean_text)

    if voiceover_lines:
        return " ".join(voiceover_lines)

    # Fallback: if format deviated, extract readable non-metadata lines
    filtered = []
    for line in script_text.splitlines():
        if any(tag in line.lower() for tag in ["visual:", "text overlay:", "manifest", "http", "#"]):
            continue
        line_clean = line.strip(" -*#")
        if len(line_clean) > 20:
            filtered.append(line_clean)

    return " ".join(filtered[:5]) or "NEPSE index is testing major resistance. Smart money is quietly accumulating while retail panics. Manage your risk."


# -----------------------------------------------------------------------------
# File Staging & Rclone Synchronization
# -----------------------------------------------------------------------------
def sync_assets_to_remote(
    staged_files: List[Path],
    remote_destination: str = DEFAULT_RCLONE_REMOTE,
) -> bool:
    """
    Syncs generated scripts, audio, and MP4 videos to Google Drive via rclone.
    Immediately deletes local files upon successful sync to free disk space on L4 server.
    """
    logger.info(f"Initiating rclone sync for {len(staged_files)} file(s) to '{remote_destination}'...")

    for file_path in staged_files:
        if not file_path.exists():
            continue

        cmd = ["rclone", "copy", str(file_path), remote_destination]
        try:
            logger.info(f"Syncing: {file_path.name} -> {remote_destination}")
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            # Immediate cleanup to save disk space
            file_path.unlink()
            logger.info(f"Successfully uploaded and cleaned up local staging file: {file_path.name}")

        except subprocess.CalledProcessError as cpe:
            logger.error(f"Failed to sync {file_path.name}. Return code: {cpe.returncode}")
            logger.error(f"rclone error output: {cpe.stderr.strip()}")
            logger.warning(f"Preserving local file {file_path} for retry.")
            raise
        except FileNotFoundError:
            logger.error("rclone executable not found. Please ensure rclone is in your PATH.")
            logger.warning(f"Preserving local file {file_path}.")
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
) -> Tuple[Path, Optional[Path]]:
    """
    End-to-End Content Generation Pipeline:
    1. Query Ollama for 30s Script
    2. Extract Voiceover Dialogue
    3. Synthesize Speech (Edge-TTS)
    4. Render 9:16 Vertical MP4 Video (MoviePy + Pillow)
    5. Sync all assets to Google Drive & Clean up local storage
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Query Ollama for viral script
    prompt = build_script_prompt(topic, context)
    system_instruction = build_system_instruction()
    script_text = query_ollama(prompt, system_instruction, model=model)

    # 2. Save script and manifest
    script_path = OUTPUT_DIR / f"faceless_script_{timestamp_str}.md"
    manifest_path = OUTPUT_DIR / f"faceless_manifest_{timestamp_str}.json"

    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_text)

    manifest_data = {
        "timestamp": datetime.now().isoformat(),
        "topic": topic or "NEPSE Market Strategy",
        "target_duration_seconds": 30,
        "format": "9:16_vertical_short",
        "resolution": "1080x1920",
        "fps": 24,
    }

    staged_items = [script_path]
    video_path = None

    # 3. Audio & Video Rendering
    if not skip_video:
        try:
            voiceover_text = extract_voiceover_lines(script_text)
            logger.info(f"Extracted Voiceover Text: \"{voiceover_text[:100]}...\"")

            audio_path = OUTPUT_DIR / f"voiceover_{timestamp_str}.mp3"
            synthesize_speech(voiceover_text, audio_path)

            # Build dynamic subtitles
            import wave
            try:
                from moviepy.editor import AudioFileClip
                a_clip = AudioFileClip(str(audio_path))
                dur = a_clip.duration
                a_clip.close()
            except Exception:
                dur = 28.0

            subtitles = split_text_into_subtitles(voiceover_text, total_duration=dur)

            # Render 9:16 MP4 Video
            video_path = OUTPUT_DIR / f"faceless_video_{timestamp_str}.mp4"
            render_short_video(audio_path, subtitles, video_path)

            staged_items.append(audio_path)
            staged_items.append(video_path)
            manifest_data["video_file"] = video_path.name
            manifest_data["audio_file"] = audio_path.name

        except Exception as ve:
            logger.error(f"Video rendering encountered an issue: {ve}", exc_info=True)
            logger.warning("Proceeding with script and manifest upload.")

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    staged_items.append(manifest_path)

    # 4. Sync assets to Google Drive via rclone & Clean up local staging
    if not skip_rclone:
        sync_assets_to_remote(staged_items, remote_destination=remote_dest)
    else:
        logger.info(f"[DRY-RUN/SKIP] Skipping rclone sync. Files preserved in {OUTPUT_DIR}")

    return script_path, video_path


def main():
    parser = argparse.ArgumentParser(
        description="Faceless Content Generator: AI script & 9:16 MP4 video generator with Google Drive sync."
    )
    parser.add_argument("--topic", type=str, default=None, help="Custom topic for the video.")
    parser.add_argument("--context", type=str, default=None, help="Additional market context.")
    parser.add_argument("--remote", type=str, default=DEFAULT_RCLONE_REMOTE, help=f"rclone destination (default: {DEFAULT_RCLONE_REMOTE}).")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL}).")
    parser.add_argument("--skip-video", action="store_true", help="Skip MP4 rendering (script only).")
    parser.add_argument("--skip-rclone", action="store_true", help="Skip rclone upload (preserve staging files).")

    args = parser.parse_args()

    try:
        run_generator(
            topic=args.topic,
            context=args.context,
            remote_dest=args.remote,
            model=args.model,
            skip_rclone=args.skip_rclone,
            skip_video=args.skip_video,
        )
        logger.info("Content Generation and Video Auto-Renderer workflow completed successfully.")
    except Exception as exc:
        logger.critical(f"Content generation failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
