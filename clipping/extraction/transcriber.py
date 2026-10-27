"""
Faster-Whisper GPU/CPU audio transcriber with word-level timestamps.
Produces both formatted transcript text for LLM and granular WordSegment tokens for subtitles.
"""

import logging
from pathlib import Path
from typing import List, Tuple

from clipping.config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
from clipping.models import WordSegment

logger = logging.getLogger("clipping.extraction.transcriber")


def transcribe_audio(
    audio_path: str,
    model_size: str = WHISPER_MODEL_SIZE,
    device: str = WHISPER_DEVICE,
    compute_type: str = WHISPER_COMPUTE_TYPE,
) -> Tuple[str, List[WordSegment]]:
    """
    Transcribes audio file using faster-whisper.
    Returns:
    1. formatted_transcript: "[MM:SS] text" for each segment.
    2. word_segments: List of WordSegment(word, start, end) with word-level timings.
    """
    from faster_whisper import WhisperModel

    active_device = device
    active_compute = compute_type

    logger.info(f"Loading WhisperModel ('{model_size}', device='{active_device}', compute='{active_compute}')...")
    try:
        model = WhisperModel(model_size, device=active_device, compute_type=active_compute)
    except Exception as e:
        logger.warning(f"Failed to load Whisper on {active_device} ({e}). Falling back to CPU...")
        active_device = "cpu"
        active_compute = "int8"
        model = WhisperModel(model_size, device=active_device, compute_type=active_compute)

    logger.info(f"Transcribing audio file: {audio_path}...")
    segments, _ = model.transcribe(
        audio_path,
        beam_size=5,
        word_timestamps=True,
    )

    formatted_lines: List[str] = []
    word_segments: List[WordSegment] = []

    for seg in segments:
        start_min = int(seg.start // 60)
        start_sec = int(seg.start % 60)
        formatted_lines.append(f"[{start_min}:{start_sec:02d}] {seg.text.strip()}")

        if seg.words:
            for w in seg.words:
                clean_w = w.word.strip()
                if clean_w:
                    word_segments.append(WordSegment(word=clean_w, start=round(w.start, 2), end=round(w.end, 2)))

    del model
    logger.info(f"Transcription complete: {len(formatted_lines)} segment(s), {len(word_segments)} word token(s).")
    return "\n".join(formatted_lines), word_segments
