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
from typing import Optional, List, Dict, Any

logger = logging.getLogger("tts_engine")

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
DEFAULT_VOICE = os.getenv("TTS_VOICE", "en-US-ChristopherNeural")
DEFAULT_RATE = os.getenv("TTS_RATE", "+10%")  # Slightly faster for 30s viral pacing
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
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Generating neural TTS with voice '{voice}' (rate={rate})...")

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


def split_text_into_subtitles(text: str, total_duration: float) -> List[Dict[str, Any]]:
    """
    Splits text into short bite-sized punchy phrases (3-6 words each)
    and distributes them across the total duration for dynamic caption overlays.
    """
    import re
    # Clean spoken text, remove markdown cues and section headers
    cleaned = re.sub(r"\[.*?\]", "", text)
    cleaned = re.sub(r"\(.*?\)", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("#", "").strip()

    sentences = [s.strip() for s in re.split(r"[.\n!?]+", cleaned) if s.strip()]
    chunks = []

    for s in sentences:
        words = s.split()
        for i in range(0, len(words), 4):  # 4 words per visual subtitle card
            chunk = " ".join(words[i:i+4])
            if chunk:
                chunks.append(chunk.upper())

    if not chunks:
        chunks = ["NEPSE MARKET UPDATE", "SMART MONEY INSIGHT", "TRADE WITH DISCIPLINE"]

    chunk_duration = total_duration / len(chunks)
    timeline = []
    current_time = 0.0

    for chunk in chunks:
        timeline.append({
            "text": chunk,
            "start": round(current_time, 2),
            "end": round(current_time + chunk_duration, 2),
            "duration": round(chunk_duration, 2),
        })
        current_time += chunk_duration

    return timeline
