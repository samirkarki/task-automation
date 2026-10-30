#!/usr/bin/env python3
"""
Professional Audio Mastering Subsystem
Mixes 0dB normalized voiceover with an ambient harmonic healing sound bed (-22dB).
Creates a broadcast-quality, documentary-grade audio track with zero clipping.
"""

import logging
import math
from pathlib import Path
from typing import Optional, Union
import numpy as np
import soundfile as sf

logger = logging.getLogger("common.audio_mastering")


def generate_ayurveda_ambient_bed(
    duration_sec: float,
    output_path: Path,
    sample_rate: int = 24000,
    target_db: float = -22.0,
) -> Path:
    """
    Synthesizes a warm, soothing ambient healing frequency bed (432Hz harmonic alignment).
    Features:
    - 108Hz (Earth root fundamental) + 216Hz + 432Hz warm upper harmonic
    - Gentle 0.15Hz breathing LFO swell
    - Capped at -22dB to sit comfortably beneath speech without competing for clarity.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False, dtype=np.float32)

    # 432Hz sacred harmonic tuning stack
    f0 = 108.0  # Warm grounding drone
    f1 = 216.0  # Body harmony
    f2 = 432.0  # Calming alpha tone

    # Slow breathing LFO modulation
    lfo = 0.75 + 0.25 * np.sin(2.0 * np.pi * 0.15 * t)

    # Smooth fades
    fade_in = np.clip(t / 1.5, 0.0, 1.0)
    fade_out = np.clip((duration_sec - t) / 2.0, 0.0, 1.0)
    envelope = fade_in * fade_out * lfo

    # Synth waveform
    drone = (
        0.55 * np.sin(2.0 * np.pi * f0 * t)
        + 0.30 * np.sin(2.0 * np.pi * f1 * t)
        + 0.15 * np.sin(2.0 * np.pi * f2 * t)
    ) * envelope

    # Apply volume scaling for target -22dB
    scale = 10.0 ** (target_db / 20.0)
    drone_scaled = (drone * scale).astype(np.float32)

    sf.write(str(output_path), drone_scaled, sample_rate)
    return output_path


def master_voice_with_ambient(
    voice_wav: Union[str, Path],
    output_wav: Union[str, Path],
    ambient_db: float = -22.0,
) -> Path:
    """
    Normalizes voiceover to 0dB peak and blends with the warm ambient healing bed.
    Produces a pristine broadcast master.
    """
    voice_path = Path(voice_wav).resolve()
    out_path = Path(output_wav).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    voice_data, sr = sf.read(str(voice_path), dtype="float32")
    if len(voice_data.shape) > 1:
        voice_data = voice_data[:, 0]  # Mono

    # 1. 0dB peak normalization of voice
    max_peak = np.max(np.abs(voice_data))
    if max_peak > 0.001:
        voice_norm = voice_data / max_peak
    else:
        voice_norm = voice_data

    duration_sec = len(voice_norm) / float(sr)

    # 2. Generate ambient drone
    ambient_temp = out_path.parent / "temp_ambient.wav"
    generate_ayurveda_ambient_bed(duration_sec, ambient_temp, sample_rate=sr, target_db=ambient_db)
    ambient_data, _ = sf.read(str(ambient_temp), dtype="float32")
    if ambient_temp.exists():
        ambient_temp.unlink()

    # 3. Sum tracks with soft headroom limiter
    mix_len = min(len(voice_norm), len(ambient_data))
    mixed = voice_norm[:mix_len] * 0.90 + ambient_data[:mix_len]

    # Soft tanh limiting to eliminate any digital clipping
    mastered = np.tanh(mixed)

    sf.write(str(out_path), mastered, sr)
    logger.info(f"[+] Mastered broadcast audio saved: {out_path} ({duration_sec:.2f}s)")
    return out_path
