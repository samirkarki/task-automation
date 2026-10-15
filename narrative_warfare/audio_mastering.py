#!/usr/bin/env python3
"""
Audio Mastering Subsystem (0dB Voice + -20dB Ambient Drone)
Mastering specifications:
- Voice track at full clarity (0dB peak normalized)
- Low-frequency ambient cinematic drone bed hard-capped at -20dB
- Vectorized sub-bass drone synthesis (38Hz - 110Hz + LFO pulse)
- Zero-clipping master mixdown with soft limiting
"""

import math
import wave
import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger("audio_mastering")


# -----------------------------------------------------------------------------
# Vectorized Dark Ambient Drone Generator
# -----------------------------------------------------------------------------
def generate_dark_cinematic_drone(
    duration_sec: float,
    output_path: Path,
    sample_rate: int = 44100,
    target_db: float = -20.0,
) -> Path:
    """
    Vectorized synthesis of a deep, psychological corporate-warfare drone track.
    Features:
    - 38Hz (sub-rumble) + 55Hz (fundamental) + 82.4Hz + 110Hz harmonics
    - Slow hypnotic 0.18Hz LFO volume undulation
    - Hard-capped at -20dB (amplitude multiplier ~ 0.10)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False, dtype=np.float32)

    # Sub-bass harmonic stack
    f0 = 38.0   # Deep visceral sub-bass
    f1 = 55.0   # Solid foundation
    f2 = 82.41  # Minor 5th tension
    f3 = 110.0  # Ominous harmonic

    # Hypnotic LFO modulation (0.18 Hz slow cycle)
    lfo = 0.72 + 0.28 * np.sin(2.0 * np.pi * 0.18 * t)

    # Fade envelope (1.5s smooth intro, 2.0s outro)
    fade_in = np.clip(t / 1.5, 0.0, 1.0)
    fade_out = np.clip((duration_sec - t) / 2.0, 0.0, 1.0)
    envelope = fade_in * fade_out * lfo

    # Multi-harmonic dark waveform
    synth = (
        0.45 * np.sin(2.0 * np.pi * f0 * t)
        + 0.35 * np.sin(2.0 * np.pi * f1 * t)
        + 0.12 * np.sin(2.0 * np.pi * f2 * t)
        + 0.08 * np.sin(2.0 * np.pi * f3 * t)
    )

    # Target -20dB amplitude calculation
    # Full scale 16-bit max = 32767. -20dB = 32767 * 10^(-20/20) = 3276.7
    linear_gain = 10.0 ** (target_db / 20.0)
    max_amp = 32767.0 * linear_gain

    drone_int16 = (synth * envelope * max_amp).clip(-max_amp, max_amp).astype(np.int16)

    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(drone_int16.tobytes())

    logger.info(f"Synthesized dark cinematic drone: {output_path.name} ({duration_sec:.1f}s, {target_db}dB)")
    return output_path


# -----------------------------------------------------------------------------
# Acoustic Mixdown & Dynamic Mastering
# -----------------------------------------------------------------------------
def read_wav_to_float(wav_path: Path) -> Tuple[np.ndarray, int]:
    """Reads 16-bit mono or stereo WAV into float32 array normalized to [-1.0, 1.0]."""
    with wave.open(str(wav_path), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sampwidth != 2:
        raise ValueError(f"Only 16-bit PCM WAV supported, got {sampwidth * 8}-bit")

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)  # Convert to mono
    return data, framerate


def master_audio_composite(
    voiceover_path: Path,
    output_master_path: Path,
    drone_db: float = -20.0,
) -> Path:
    """
    Performs precise audio mastering:
    - Normalizes voice track to full clarity (0dB)
    - Concurrently overlays low-frequency ambient cinematic drone at -20dB
    - Applies soft knee limiting to prevent distortion and clipping
    """
    output_master_path.parent.mkdir(parents=True, exist_ok=True)
    voice_data, sample_rate = read_wav_to_float(voiceover_path)
    duration_sec = len(voice_data) / float(sample_rate)

    # 1. Normalize voice to 0dB (peak = 0.999)
    peak = np.max(np.abs(voice_data))
    if peak > 0:
        voice_data = voice_data * (0.995 / peak)

    # 2. Generate synchronized ambient drone
    temp_drone = output_master_path.parent / "temp_ambient_drone.wav"
    generate_dark_cinematic_drone(duration_sec, temp_drone, sample_rate=sample_rate, target_db=drone_db)
    drone_data, drone_rate = read_wav_to_float(temp_drone)

    # Adjust lengths if mismatched
    min_len = min(len(voice_data), len(drone_data))
    voice_data = voice_data[:min_len]
    drone_data = drone_data[:min_len]

    # 3. Master Mix with Soft Limiting
    # Voice dominates (0dB), Drone stays hard-capped at -20dB
    mixed = voice_data + drone_data
    # Soft limiter curve (tanh soft clipping) when sum exceeds 0.98
    limit_threshold = 0.95
    over = np.abs(mixed) > limit_threshold
    if np.any(over):
        # Soft saturation compress peaks without harsh digital clipping
        excess = np.abs(mixed) - limit_threshold
        compressed = limit_threshold + (1.0 - limit_threshold) * np.tanh(excess / (1.0 - limit_threshold))
        mixed = np.sign(mixed) * np.where(over, compressed, np.abs(mixed))

    # Convert back to 16-bit PCM
    master_int16 = np.clip(mixed * 32767.0, -32767, 32767).astype(np.int16)

    with wave.open(str(output_master_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(master_int16.tobytes())

    if temp_drone.exists():
        temp_drone.unlink()

    logger.info(f"Mastered studio audio compiled: {output_master_path} (Voice=0dB, Drone={drone_db}dB)")
    return output_master_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_out = Path("test_drone.wav")
    generate_dark_cinematic_drone(15.0, test_out)
    print(f"Generated test drone: {test_out} ({test_out.stat().st_size} bytes)")
    test_out.unlink()
