#!/usr/bin/env python3
"""
Precise Word-Level Transcription & Kinetic Subtitle Engine
Integrates Faster-Whisper (base model) to extract millisecond word timestamps
and compute dynamic typography scale factors based on speech velocity.

Features:
- Word-level timestamps (start_ms, end_ms, confidence)
- Speech velocity analysis (words/second)
- Typography scale factor modulation
- Caption keyword emphasis tagging
- Deterministic fallback alignment if Faster-Whisper is initializing or offline
"""

import os
import re
import sys
import wave
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger("whisper_transcriber")

DEFAULT_WHISPER_MODEL = os.getenv("WHISPER_MODEL_SIZE", "base")


@dataclass
class WordTimestamp:
    word: str
    start: float  # seconds
    end: float    # seconds
    probability: float
    is_emphasis: bool = False
    velocity_scale: float = 1.0  # Scale factor for typography sizing

    @property
    def duration(self) -> float:
        return max(0.05, self.end - self.start)


@dataclass
class SubtitleCard:
    text: str
    start: float
    end: float
    words: List[WordTimestamp]
    velocity_scale: float = 1.0
    has_emphasis: bool = False


# -----------------------------------------------------------------------------
# Speech Velocity & Typography Scaling
# -----------------------------------------------------------------------------
def calculate_velocity_scale(words_per_sec: float) -> float:
    """
    Modulates typography scale factor based on speech velocity:
    - High velocity (>3.2 wps): Scale down (0.88x - 0.95x) to maintain balance.
    - Normal velocity (2.2 - 3.2 wps): Standard scale (1.0x).
    - Slow / dramatic cadence (<2.0 wps): Scale up (1.10x - 1.25x) for emphasis.
    """
    if words_per_sec > 3.6:
        return 0.88
    elif words_per_sec > 3.0:
        return 0.94
    elif words_per_sec < 1.6:
        return 1.22
    elif words_per_sec < 2.2:
        return 1.12
    return 1.0


def group_words_into_kinetic_cards(
    word_timestamps: List[WordTimestamp],
    max_words_per_card: int = 3,
    max_duration_sec: float = 1.6,
) -> List[SubtitleCard]:
    """
    Groups individual word timestamps into punchy, rapid-fire vertical subtitle cards
    (1-3 words per card) typical of elite retention short-form videos.
    """
    if not word_timestamps:
        return []

    cards: List[SubtitleCard] = []
    current_words: List[WordTimestamp] = []
    card_start = word_timestamps[0].start

    for w in word_timestamps:
        current_words.append(w)
        duration = w.end - card_start

        # Break card if max words reached or natural punctuation pause encountered
        is_punct = bool(re.search(r"[\.,!\?;:]$", w.word))
        if len(current_words) >= max_words_per_card or duration >= max_duration_sec or is_punct:
            card_end = w.end
            total_duration = max(0.2, card_end - card_start)
            wps = len(current_words) / total_duration
            card_velocity_scale = calculate_velocity_scale(wps)

            card_has_emphasis = any(item.is_emphasis for item in current_words)

            cards.append(
                SubtitleCard(
                    text=" ".join(item.word for item in current_words),
                    start=card_start,
                    end=card_end,
                    words=list(current_words),
                    velocity_scale=card_velocity_scale,
                    has_emphasis=card_has_emphasis,
                )
            )
            current_words = []
            card_start = w.end

    if current_words:
        card_end = current_words[-1].end
        total_duration = max(0.2, card_end - card_start)
        wps = len(current_words) / total_duration
        cards.append(
            SubtitleCard(
                text=" ".join(item.word for item in current_words),
                start=card_start,
                end=card_end,
                words=current_words,
                velocity_scale=calculate_velocity_scale(wps),
                has_emphasis=any(item.is_emphasis for item in current_words),
            )
        )

    return cards


# -----------------------------------------------------------------------------
# Device & Precision Detection
# -----------------------------------------------------------------------------
def detect_whisper_device() -> Tuple[str, str]:
    """
    Detects the best available device ('cuda' or 'cpu') and compute precision.
    Does not require PyTorch: queries CTranslate2 directly, or checks torch if installed.
    Allows manual override via WHISPER_DEVICE env var ('cuda', 'cpu', 'auto').
    """
    forced_device = os.getenv("WHISPER_DEVICE", "").strip().lower()
    if forced_device in ("cuda", "gpu"):
        return "cuda", "float16"
    if forced_device == "cpu":
        return "cpu", "int8"
    if forced_device == "auto":
        return "auto", "auto"

    has_cuda = False
    try:
        import ctranslate2
        has_cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        pass

    if not has_cuda:
        try:
            import torch
            has_cuda = bool(torch.cuda.is_available())
        except Exception:
            pass

    if has_cuda:
        return "cuda", "float16"
    return "cpu", "int8"


# -----------------------------------------------------------------------------
# Faster-Whisper Extraction
# -----------------------------------------------------------------------------
def transcribe_with_faster_whisper(
    audio_path: Path,
    model_size: str = DEFAULT_WHISPER_MODEL,
    emphasis_keywords: Optional[List[str]] = None,
) -> List[WordTimestamp]:
    """
    Transcribes audio using Faster-Whisper and extracts exact word-level millisecond timestamps.
    Safely falls back to CPU if GPU/cuDNN execution fails, and returns an empty list on failure
    so the pipeline gracefully proceeds with calibrated phonetic fallback.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.warning("faster-whisper is not installed in the active environment.")
        return []

    device, compute_type = detect_whisper_device()
    logger.info(f"Loading Faster-Whisper model '{model_size}' on device '{device}' ({compute_type})...")

    model = None
    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception as e:
        if device != "cpu":
            logger.warning(f"Failed to initialize Faster-Whisper on {device} ({e}). Retrying on CPU...")
            try:
                model = WhisperModel(model_size, device="cpu", compute_type="int8")
            except Exception as e_cpu:
                logger.warning(f"Failed to load Faster-Whisper on CPU: {e_cpu}")
                return []
        else:
            logger.warning(f"Failed to load Faster-Whisper model: {e}")
            return []

    try:
        segments, info = model.transcribe(str(audio_path), word_timestamps=True, language="en")

        cleaned_keywords = [k.upper().strip() for k in (emphasis_keywords or [])]

        word_records: List[WordTimestamp] = []
        for segment in segments:
            for w in segment.words:
                clean_word = w.word.strip()
                stripped_word = re.sub(r"[^\w]", "", clean_word).upper()
                is_emp = any(k in stripped_word or stripped_word in k for k in cleaned_keywords) if stripped_word else False
                word_records.append(
                    WordTimestamp(
                        word=clean_word,
                        start=round(w.start, 3),
                        end=round(w.end, 3),
                        probability=round(w.probability, 3),
                        is_emphasis=is_emp,
                    )
                )

        logger.info(f"Faster-Whisper transcribed {len(word_records)} words with exact millisecond timestamps.")
        return word_records
    except Exception as e:
        logger.warning(f"Faster-Whisper transcription failed during processing: {e}. Falling back to cadence algorithm.")
        return []


# -----------------------------------------------------------------------------
# Calibrated Phonetic / Syllabic Fallback
# -----------------------------------------------------------------------------
def get_audio_duration_sec(audio_path: Path) -> float:
    """Gets audio duration in seconds from WAV header."""
    try:
        with wave.open(str(audio_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate)
    except Exception:
        return 30.0


def transcribe_fallback_cadence(
    spoken_text: str,
    audio_path: Path,
    emphasis_keywords: Optional[List[str]] = None,
) -> List[WordTimestamp]:
    """
    Fallback alignment algorithm that distributes word timings proportionally
    across the known audio duration based on character length and phonetic pauses.
    """
    duration = get_audio_duration_sec(audio_path)
    words = spoken_text.split()
    if not words:
        return []

    cleaned_keywords = [k.upper().strip() for k in (emphasis_keywords or [])]

    # Weighted duration by character count + punctuation pause
    weights = []
    for w in words:
        weight = len(w) + (2.0 if re.search(r"[\.,!\?;:]$", w) else 0.0)
        weights.append(weight)
    total_weight = sum(weights)

    timestamps: List[WordTimestamp] = []
    curr_t = 0.0
    for idx, w in enumerate(words):
        w_dur = (weights[idx] / total_weight) * duration
        w_start = round(curr_t, 3)
        w_end = round(curr_t + w_dur, 3)
        curr_t += w_dur

        stripped = re.sub(r"[^\w]", "", w).upper()
        is_emp = any(k in stripped or stripped in k for k in cleaned_keywords) if stripped else False

        timestamps.append(
            WordTimestamp(
                word=w,
                start=w_start,
                end=w_end,
                probability=1.0,
                is_emphasis=is_emp,
            )
        )

    logger.info(f"Generated {len(timestamps)} calibrated fallback word timestamps across {duration:.2f}s.")
    return timestamps


# -----------------------------------------------------------------------------
# Unified Transcription Dispatcher
# -----------------------------------------------------------------------------
def generate_kinetic_subtitles(
    audio_path: Path,
    spoken_text: str,
    emphasis_keywords: Optional[List[str]] = None,
) -> List[SubtitleCard]:
    """
    High-level entry point that returns kinetic subtitle cards with word-level
    millisecond timestamps and speech velocity scale factors.
    """
    word_timestamps: List[WordTimestamp] = []
    try:
        word_timestamps = transcribe_with_faster_whisper(audio_path, emphasis_keywords=emphasis_keywords)
    except Exception as e:
        logger.warning(f"Faster-Whisper encountered unexpected exception: {e}. Falling back to cadence algorithm.")
        word_timestamps = []

    if not word_timestamps:
        logger.info("Using calibrated fallback cadence alignment for kinetic subtitles.")
        word_timestamps = transcribe_fallback_cadence(spoken_text, audio_path, emphasis_keywords)

    return group_words_into_kinetic_cards(word_timestamps)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dummy_wav = Path("test_voice.wav")
    text = "In 1985, Steve Jobs was humiliated and fired by the CEO he recruited."
    from narrative_warfare.voiceover_studio import synthesize_mock_voice
    synthesize_mock_voice(text, dummy_wav)
    cards = generate_kinetic_subtitles(dummy_wav, text, emphasis_keywords=["HUMILIATED", "FIRED"])
    for c in cards:
        print(f"[{c.start:.2f}s - {c.end:.2f}s] (scale={c.velocity_scale:.2f}, emp={c.has_emphasis}) -> {c.text}")
    dummy_wav.unlink()
