"""
Audio Peak & Silence Boundary Detector.
Analyzes audio waveforms for volume/scream spikes and natural silence gaps
so clips snap cleanly to the start and end of speech without mid-word cutoffs.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import soundfile as sf

logger = logging.getLogger("clipping.extraction.audio_peak_detector")


def analyze_audio_energy(
    audio_path: Union[str, Path],
    frame_size_sec: float = 0.1,  # 100ms analysis window
    hop_size_sec: float = 0.05,    # 50ms hop
) -> Dict[str, Any]:
    """
    Computes RMS decibel envelope and identifies scream/loudness peaks and silence intervals.
    """
    path = Path(audio_path).resolve()
    if not path.exists():
        logger.warning(f"Audio file not found for peak analysis: {path}")
        return {"peaks": [], "silences": [], "duration": 0.0}

    try:
        data, sr = sf.read(str(path), dtype="float32")
    except Exception as e:
        logger.warning(f"Could not read audio with soundfile ({e}). Falling back.")
        return {"peaks": [], "silences": [], "duration": 0.0}

    # Downmix to mono if stereo
    if len(data.shape) > 1:
        data = np.mean(data, axis=1)

    total_samples = len(data)
    total_sec = total_samples / float(sr)

    frame_len = max(1, int(frame_size_sec * sr))
    hop_len = max(1, int(hop_size_sec * sr))

    # Compute RMS energy per frame
    rms_values = []
    timestamps = []

    for start in range(0, total_samples - frame_len, hop_len):
        frame = data[start : start + frame_len]
        rms = np.sqrt(np.mean(frame ** 2) + 1e-12)
        rms_db = 20.0 * np.log10(rms)
        rms_values.append(rms_db)
        timestamps.append(start / float(sr))

    if not rms_values:
        return {"peaks": [], "silences": [], "duration": total_sec}

    rms_arr = np.array(rms_values, dtype=np.float32)
    time_arr = np.array(timestamps, dtype=np.float32)

    # Median and standard deviation of volume
    median_db = float(np.median(rms_arr))
    std_db = float(np.std(rms_arr))

    # Silence threshold: anything below -38dB or 10dB below median when speech is present
    if median_db < -40.0:
        silence_thresh_db = -38.0
    else:
        silence_thresh_db = min(-35.0, median_db - 10.0)

    # Loudness/scream threshold: 1.8 standard deviations above median or > -12dB
    spike_thresh_db = max(-14.0, median_db + 1.8 * std_db)

    # 1. Identify silence intervals [start_sec, end_sec]
    is_silent = rms_arr < silence_thresh_db
    silences: List[Tuple[float, float]] = []
    in_silence = False
    s_start = 0.0

    for i, silent in enumerate(is_silent):
        t = time_arr[i]
        if silent and not in_silence:
            in_silence = True
            s_start = t
        elif not silent and in_silence:
            in_silence = False
            if (t - s_start) >= 0.25:  # At least 250ms of silence
                silences.append((round(s_start, 2), round(t, 2)))

    if in_silence and (total_sec - s_start) >= 0.25:
        silences.append((round(s_start, 2), round(total_sec, 2)))

    # 2. Identify scream / loud reaction peaks [timestamp, peak_db, intensity_ratio]
    peaks: List[Tuple[float, float, float]] = []
    for i in range(1, len(rms_arr) - 1):
        if rms_arr[i] > spike_thresh_db:
            # Local maximum check
            if rms_arr[i] >= rms_arr[i - 1] and rms_arr[i] >= rms_arr[i + 1]:
                rel_intensity = (rms_arr[i] - median_db) / (std_db + 1e-6)
                peaks.append((round(float(time_arr[i]), 2), round(float(rms_arr[i]), 1), round(rel_intensity, 2)))

    # Deduplicate peaks within 3 seconds (keep the highest)
    filtered_peaks: List[Tuple[float, float, float]] = []
    peaks.sort(key=lambda x: x[0])
    for p in peaks:
        if not filtered_peaks:
            filtered_peaks.append(p)
        else:
            prev = filtered_peaks[-1]
            if (p[0] - prev[0]) < 3.0:
                if p[1] > prev[1]:
                    filtered_peaks[-1] = p
            else:
                filtered_peaks.append(p)

    logger.info(
        f"Audio analysis complete: {len(filtered_peaks)} loudness/scream peak(s), "
        f"{len(silences)} silence gap(s) over {total_sec:.1f}s."
    )

    return {
        "peaks": filtered_peaks,
        "silences": silences,
        "duration": total_sec,
        "median_db": median_db,
    }


def find_clean_silence_boundary(
    target_sec: float,
    silences: List[Tuple[float, float]],
    direction: str = "before",  # "before" or "after"
    max_search_sec: float = 6.0,
) -> float:
    """
    Finds the nearest silence gap to cleanly cut audio without chopping a word.
    Direction 'before': searches backwards from target_sec.
    Direction 'after': searches forward from target_sec.
    """
    if not silences:
        return target_sec

    best_cut = target_sec

    if direction == "before":
        candidates = [
            (s_start, s_end)
            for s_start, s_end in silences
            if (target_sec - max_search_sec) <= s_end <= (target_sec + 1.0)
        ]
        if candidates:
            # Pick the silence gap closest to target_sec, cutting at mid-silence
            closest = max(candidates, key=lambda x: x[1])
            best_cut = (closest[0] + closest[1]) / 2.0
    else:  # "after"
        candidates = [
            (s_start, s_end)
            for s_start, s_end in silences
            if (target_sec - 1.0) <= s_start <= (target_sec + max_search_sec)
        ]
        if candidates:
            closest = min(candidates, key=lambda x: x[0])
            best_cut = (closest[0] + closest[1]) / 2.0

    return round(best_cut, 2)
