#!/usr/bin/env python3
"""
Text-to-Speech (TTS) Engine for Faceless Content Automation
Supports Edge-TTS high-quality neural voices with speed/pitch controls,
word/segment timestamps for on-screen subtitles, and graceful fallbacks.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

logger = logging.getLogger("tts_engine")

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
DEFAULT_VOICE = os.getenv("TTS_VOICE", "ne-NP-SagarNeural")
DEFAULT_RATE = os.getenv("TTS_RATE", "+0%")  # Natural human conversational speed
DEFAULT_PITCH = os.getenv("TTS_PITCH", "+0Hz")


# -----------------------------------------------------------------------------
# Edge-TTS Engine Implementation
# -----------------------------------------------------------------------------
async def _async_generate_edge_tts(
    text: str,
    output_path: Path,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> Path:
    """
    Generates audio using edge-tts async API.
    """
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(str(output_path))
    return output_path


def generate_speech_edge(
    text: str,
    output_path: Path,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
) -> Path:
    """
    Synchronous wrapper for generating speech via Edge-TTS.
    Automatically switches to human Nepali neural voice if Devanagari script is detected.
    """
    import re

    # Auto-switch to human Nepali neural voice if Devanagari characters are present
    if re.search(r"[\u0900-\u097F]", text) and not voice.startswith("ne-"):
        logger.info(
            f"Devanagari text detected. Auto-routing voice from '{voice}' to "
            f"human Nepali neural voice 'ne-NP-SagarNeural'."
        )
        voice = "ne-NP-SagarNeural"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Generating human neural TTS with voice '{voice}' (rate={rate}, pitch={pitch})...")

    try:
        # Run event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_async_generate_edge_tts(text, output_path, voice, rate, pitch))
        finally:
            loop.close()

        logger.info(f"Audio voiceover successfully generated at: {output_path} ({output_path.stat().st_size} bytes)")
        return output_path

    except Exception as e:
        logger.error(f"Edge-TTS generation failed: {e}")
        raise


# -----------------------------------------------------------------------------
# Offline Fallback Generator
# -----------------------------------------------------------------------------
def generate_fallback_silence_or_tone(text: str, output_path: Path, words_per_second: float = 2.5) -> Path:
    """
    Fallback method that generates a placeholder audio file if neural TTS is unavailable.
    Calculates estimated reading duration based on word count.
    """
    import wave
    import struct
    import math

    output_path.parent.mkdir(parents=True, exist_ok=True)
    word_count = len(text.split())
    duration_sec = max(3.0, word_count / words_per_second)
    sample_rate = 44100
    num_samples = int(duration_sec * sample_rate)

    logger.warning(
        f"Using fallback audio generator. Creating placeholder audio ({duration_sec:.1f}s) at {output_path}..."
    )

    with wave.open(str(output_path), "w") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        # Generate a faint warm ambient tone (432Hz sine wave)
        for i in range(num_samples):
            t = float(i) / sample_rate
            value = int(500 * math.sin(2.0 * math.pi * 432.0 * t))
            data = struct.pack("<h", value)
            wav_file.writeframes(data)

    return output_path


# -----------------------------------------------------------------------------
# Main Public Interface
# -----------------------------------------------------------------------------
def synthesize_speech(
    text: str,
    output_path: Path,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
) -> Path:
    """
    Synthesizes speech from text. Tries Edge-TTS first; falls back gracefully if necessary.
    """
    selected_voice = voice or DEFAULT_VOICE
    selected_rate = rate or DEFAULT_RATE

    try:
        return generate_speech_edge(text, output_path, voice=selected_voice, rate=selected_rate)
    except Exception as exc:
        logger.warning(f"Neural TTS failed ({exc}). Falling back to audio placeholder...")
        return generate_fallback_silence_or_tone(text, output_path)


def split_text_into_subtitles(
    captions_or_text: Union[str, List[str]],
    total_duration: float,
) -> List[Dict[str, Any]]:
    """
    Creates synchronized subtitle timeline for video overlays.
    - If a list of English caption strings is provided, distributes them across total_duration.
    - If a single string is provided, splits into short 3-5 word punchy chunks.
    Proportionally allocates screen duration according to word count so viewers can comfortably read.
    """
    import re

    chunks: List[str] = []

    if isinstance(captions_or_text, list):
        for item in captions_or_text:
            cleaned = str(item).strip().replace("**", "").replace("#", "")
            cleaned = re.sub(r"\[.*?\]", "", cleaned)
            cleaned = re.sub(r"\(.*?\)", "", cleaned).strip()
            if cleaned:
                chunks.append(cleaned.upper())
    else:
        text = str(captions_or_text)
        cleaned = re.sub(r"\[.*?\]", "", text)
        cleaned = re.sub(r"\(.*?\)", "", cleaned)
        cleaned = cleaned.replace("**", "").replace("#", "").strip()

        sentences = [s.strip() for s in re.split(r"[.\n!?]+", cleaned) if s.strip()]
        for s in sentences:
            words = s.split()
            for i in range(0, len(words), 4):  # 4 words per visual subtitle card
                chunk = " ".join(words[i : i + 4])
                if chunk:
                    chunks.append(chunk.upper())

    if not chunks:
        chunks = [
            "NEPSE MARKET WARNING",
            "RETAIL TRADERS TRAPPED AT 2800",
            "SMART MONEY ACCUMULATION",
            "SET YOUR STRICT STOPLOSS",
            "TRADE WITH DISCIPLINE",
        ]

    # Proportional screen timing based on word count
    word_counts = [max(1, len(c.split())) for c in chunks]
    total_words = sum(word_counts)

    timeline: List[Dict[str, Any]] = []
    current_time = 0.0

    for idx, chunk in enumerate(chunks):
        if idx == len(chunks) - 1:
            end_time = total_duration
        else:
            fraction = word_counts[idx] / total_words
            card_dur = max(1.5, fraction * total_duration)
            end_time = min(total_duration - 1.0, current_time + card_dur)

        timeline.append(
            {
                "text": chunk,
                "start": round(current_time, 2),
                "end": round(end_time, 2),
                "duration": round(max(0.2, end_time - current_time), 2),
            }
        )
        current_time = end_time
        if current_time >= total_duration:
            break

    return timeline
