#!/usr/bin/env python3
"""
Faceless Content Generator
Queries local Ollama (qwen3-coder:30b) to draft viral 30-second short-form financial
scripts (TikTok/Reels/Shorts), stages script and asset files in faceless_content/output/,
and synchronizes them to Google Drive via rclone, cleaning up local storage on success.
"""

import os
import sys
import json
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

import requests

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
            "temperature": 0.7,  # slightly higher temperature for creative viral hooks
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
    except requests.exceptions.HTTPError as he:
        logger.error(f"Ollama HTTP error occurred: {he}")
        raise
    except Exception as ex:
        logger.error(f"Unexpected error querying Ollama: {ex}")
        raise


# -----------------------------------------------------------------------------
# Viral Script Prompt Construction
# -----------------------------------------------------------------------------
def build_script_prompt(topic: Optional[str] = None, market_context: Optional[str] = None) -> str:
    """
    Constructs the prompt for drafting a viral 30-second short-form financial script.
    """
    active_topic = topic or "Why 90% of NEPSE retail traders lose money right before a bull run breakout"
    context_str = market_context or "Recent NEPSE turnover spike, sector rotation from commercial banks to hydropower, interest rate cuts."

    prompt = f"""
Write a high-retention, viral 30-second short-form video script (TikTok, YouTube Shorts, Instagram Reels) for a faceless financial channel focusing on the Nepal Stock Exchange (NEPSE).

Topic: {active_topic}
Market Context: {context_str}

Format Requirements:
- Exact Pacing: Total spoken words must be strictly between 65 to 80 words (approximately 28-32 seconds of rapid, clear speech).
- Language: English (or Romanized Nepali mixed with English terms commonly used by traders, clear and crisp).
- Tone: Punchy, urgent, high-status, psychological, no fluff.

Structure the script into these explicit sections:

1. [HOOK] (00:00 - 00:03)
   - Visual: Aggressive zoom-in or striking visual text.
   - Audio/Voiceover: High-curiosity question or controversial financial truth.
   - Text Overlay: Bold 3-4 word curiosity trap.

2. [PROBLEM & TRAP] (00:03 - 00:12)
   - Visual: Fast b-roll cues (red candles, panic selling, institutional accumulation).
   - Voiceover: Explaining the psychological trap everyday investors fall into.
   - Text Overlay: Key emotional triggers.

3. [THE INSIDER INSIGHT] (00:12 - 00:23)
   - Visual: Green breakout charts, volume indicator spikes, smart money heatmaps.
   - Voiceover: The non-obvious rule or data metric smart money uses.
   - Text Overlay: The actionable rule.

4. [CALL TO ACTION & OUTRO] (00:23 - 00:30)
   - Visual: Follow animation / comment trigger.
   - Voiceover: Specific debate-starter question to blow up the comment section.
   - Text Overlay: "Save this before your next trade."

5. [PRODUCTION ASSETS & B-ROLL MANIFEST]
   - List 4 precise royalty-free B-Roll search keywords (e.g., 'stock market red panic', 'money counting slow motion').
   - Recommended background music vibe (e.g., 'Phonk / Dark Cinematic Suspense').
   - On-screen caption styling suggestions.
"""
    return prompt.strip()


def build_system_instruction() -> str:
    """
    System prompt enforcing viral short-form retention mechanics.
    """
    return (
        "You are an award-winning short-form video director and viral financial scriptwriter. "
        "You master 30-second hooks, dopamine-driven storytelling, viewer retention curves, "
        "and clean visual cue prompts for faceless video automation channels."
    )


# -----------------------------------------------------------------------------
# File Staging & Rclone Synchronization
# -----------------------------------------------------------------------------
def save_script_locally(
    script_content: str,
    topic: Optional[str] = None,
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    """
    Saves the generated script and asset metadata to the staging directory.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Generate Markdown script file
    script_filename = f"faceless_script_{timestamp_str}.md"
    script_path = output_dir / script_filename

    # Also generate metadata manifest for downstream video rendering pipelines
    manifest_filename = f"faceless_manifest_{timestamp_str}.json"
    manifest_path = output_dir / manifest_filename

    manifest_data = {
        "timestamp": datetime.now().isoformat(),
        "topic": topic or "NEPSE Market Strategy",
        "target_duration_seconds": 30,
        "script_file": script_filename,
        "format": "9:16_vertical_short",
        "platform": ["tiktok", "instagram_reels", "youtube_shorts"],
    }

    logger.info(f"Saving staged script to {script_path}...")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    logger.info(f"Staged script and manifest created successfully.")
    return script_path


def sync_assets_to_remote(
    staged_files: List[Path],
    remote_destination: str = DEFAULT_RCLONE_REMOTE,
) -> bool:
    """
    Syncs generated scripts and assets to Google Drive via rclone.
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
# Main Execution Flow
# -----------------------------------------------------------------------------
def run_generator(
    topic: Optional[str] = None,
    context: Optional[str] = None,
    remote_dest: str = DEFAULT_RCLONE_REMOTE,
    model: str = DEFAULT_MODEL,
    skip_rclone: bool = False,
) -> Path:
    """
    Executes the complete content generation and asset sync pipeline.
    """
    # 1. Build prompt
    prompt = build_script_prompt(topic, context)
    system_instruction = build_system_instruction()

    # 2. Query Ollama
    script_text = query_ollama(
        prompt=prompt,
        system_instruction=system_instruction,
        model=model,
    )

    # 3. Save locally to staging
    script_path = save_script_locally(script_text, topic=topic, output_dir=OUTPUT_DIR)
    manifest_path = script_path.with_name(script_path.name.replace("faceless_script_", "faceless_manifest_").replace(".md", ".json"))

    staged_items = [script_path]
    if manifest_path.exists():
        staged_items.append(manifest_path)

    # 4. Sync to remote Google Drive and clean up
    if not skip_rclone:
        sync_assets_to_remote(staged_items, remote_destination=remote_dest)
    else:
        logger.info(f"[DRY-RUN/SKIP] Skipping rclone sync. Files saved in {OUTPUT_DIR}")

    return script_path


def main():
    parser = argparse.ArgumentParser(
        description="Faceless Content Generator: AI script & asset generator with Google Drive sync."
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Custom topic for the 30-second financial video.",
    )
    parser.add_argument(
        "--context",
        type=str,
        default=None,
        help="Additional market context or trading data highlights.",
    )
    parser.add_argument(
        "--remote",
        type=str,
        default=DEFAULT_RCLONE_REMOTE,
        help=f"rclone destination remote (default: {DEFAULT_RCLONE_REMOTE}).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Ollama model name (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--skip-rclone",
        action="store_true",
        help="Skip rclone upload (useful for local development/testing).",
    )

    args = parser.parse_args()

    try:
        run_generator(
            topic=args.topic,
            context=args.context,
            remote_dest=args.remote,
            model=args.model,
            skip_rclone=args.skip_rclone,
        )
        logger.info("Faceless Content Generator workflow completed successfully.")
    except Exception as exc:
        logger.critical(f"Faceless Content Generator aborted with error: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
