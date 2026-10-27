"""
Neural Text-to-Speech (TTS) narrator for commentary voiceovers using Edge-TTS.
Generates crystal-clear narration with optimal conversational pacing for short-form video.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("clipping.transformation.tts_narrator")

DEFAULT_VOICE = os.getenv("TTS_VOICE_EN", "en-US-GuyNeural")
DEFAULT_RATE = os.getenv("TTS_RATE_EN", "+4%")
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
    Synchronously synthesizes neural speech audio to output_path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sel_voice = voice or DEFAULT_VOICE
    sel_rate = rate or DEFAULT_RATE
    sel_pitch = pitch or DEFAULT_PITCH

    logger.info(f"Synthesizing commentary narration with '{sel_voice}' (rate={sel_rate})...")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_async_synthesize(text, output_path, sel_voice, sel_rate, sel_pitch))
        finally:
            loop.close()

        logger.info(f"Narration generated at {output_path} ({output_path.stat().st_size} bytes).")
        return output_path
    except Exception as e:
        logger.warning(f"Edge-TTS failed ({e}). Generating fallback audio tone...")
        import wave
        import struct
        import math

        words = len(text.split())
        dur = max(3.0, words / 2.5)
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
