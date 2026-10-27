"""
Soothing Human Neural Speech Synthesis Engine.
Replaces robotic announcer voices with warm, calming, natural human voices
(e.g., Andrew Multilingual, Brian, Christopher) with relaxed human pacing.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("clipping.transformation.tts_narrator")

# Soothing, natural human voice presets
SOOTHING_VOICES = {
    "andrew": "en-US-AndrewMultilingualNeural",   # Warm, authoritative, conversational podcast host
    "brian": "en-US-BrianMultilingualNeural",     # Gentle, calm, soothing human tone
    "christopher": "en-US-ChristopherNeural",     # Deep, mature, soothing documentary narrator
    "ava": "en-US-AvaMultilingualNeural",         # Warm, expressive, soothing female voice
    "ryan": "en-GB-RyanNeural",                   # Refined, calm British narrator
}

DEFAULT_VOICE = os.getenv("TTS_VOICE_EN", SOOTHING_VOICES["andrew"])
DEFAULT_RATE = os.getenv("TTS_RATE_EN", "+0%")  # Relaxed, natural human cadence (not rushed)
DEFAULT_PITCH = os.getenv("TTS_PITCH_EN", "+0Hz")


async def _async_synthesize(text: str, output_path: Path, voice: str, rate: str, pitch: str) -> Path:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(str(output_path))
    return output_path


def generate_narration(
    text: str,
    output_path: Path,
    voice: Optional[str] = None,
    rate: Optional[str] = None,
    pitch: Optional[str] = None,
) -> Path:
    """
    Synchronously synthesizes soothing human neural speech audio to output_path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Resolve preset name if alias was given (e.g. 'brian' -> 'en-US-BrianMultilingualNeural')
    selected_voice = SOOTHING_VOICES.get(voice, voice) if voice else DEFAULT_VOICE
    selected_rate = rate or DEFAULT_RATE
    selected_pitch = pitch or DEFAULT_PITCH

    logger.info(f"Synthesizing soothing human narration with '{selected_voice}' (rate={selected_rate})...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_async_synthesize(text, output_path, selected_voice, selected_rate, selected_pitch))
        finally:
            loop.close()

        logger.info(f"Soothing voiceover audio generated at: {output_path} ({output_path.stat().st_size} bytes).")
        return output_path
    except Exception as e:
        logger.warning(f"Edge-TTS failed ({e}). Generating fallback audio tone...")
        import wave
        import struct
        import math

        words = len(text.split())
        dur = max(3.0, words / 2.3)
        sample_rate = 44100
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            for i in range(int(dur * sample_rate)):
                t = float(i) / sample_rate
                val = int(800 * math.sin(2.0 * math.pi * 220.0 * t))
                wav_file.writeframes(struct.pack("<h", val))
        return output_path
