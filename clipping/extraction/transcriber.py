"""
Faster-Whisper GPU/CPU audio transcriber with word-level timestamps and PyAV compatibility shield.
Produces both formatted transcript text for LLM and granular WordSegment tokens for subtitles.
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple, Union
import numpy as np

from clipping.config import WHISPER_MODEL_SIZE, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE
from clipping.models import WordSegment

logger = logging.getLogger("clipping.extraction.transcriber")

# PyAV Compatibility Shield:
# In certain PyAV versions, av.open does not accept metadata_errors="ignore",
# which causes faster-whisper's decode_audio to crash with a TypeError.
try:
    import av
    _orig_av_open = av.open

    def _safe_av_open(*args, **kwargs):
        try:
            return _orig_av_open(*args, **kwargs)
        except TypeError as err:
            if "metadata_errors" in str(err):
                kwargs.pop("metadata_errors", None)
                return _orig_av_open(*args, **kwargs)
            raise

    av.open = _safe_av_open
    logger.debug("PyAV open() compatibility patch registered.")
except Exception:
    pass


def load_audio_waveform(audio_path: Union[str, Path], target_sr: int = 16000) -> Optional[np.ndarray]:
    """
    Decodes audio to float32 16kHz mono numpy array using soundfile.
    Bypasses PyAV completely if needed.
    """
    try:
        import soundfile as sf
        data, sr = sf.read(str(audio_path), dtype="float32")
        if len(data.shape) > 1:
            data = np.mean(data, axis=1)  # Mono

        if sr != target_sr:
            # Resample to 16kHz for Whisper
            from scipy.signal import resample
            num_samples = int(len(data) * float(target_sr) / float(sr))
            data = resample(data, num_samples).astype(np.float32)

        return data
    except Exception as e:
        logger.debug(f"Direct soundfile audio loading failed ({e}). Whisper will use default decoder.")
        return None


def transcribe_audio(
    audio_path: str,
    model_size: str = WHISPER_MODEL_SIZE,
    device: str = WHISPER_DEVICE,
    compute_type: str = WHISPER_COMPUTE_TYPE,
    offset_seconds: float = 0.0,
) -> Tuple[str, List[WordSegment]]:
    """
    Transcribes audio using faster-whisper.
    Accepts an optional offset_seconds to align section-sliced audio with original VOD timestamps.
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
        logger.warning(f"Failed to load Whisper on {active_device} ({e}). Falling back to CPU int8...")
        active_device = "cpu"
        active_compute = "int8"
        model = WhisperModel(model_size, device=active_device, compute_type=active_compute)

    logger.info(f"Transcribing audio file: {audio_path} (offset={offset_seconds:.1f}s)...")

    # Try transcribing directly with audio_path; if PyAV still complains, decode via soundfile numpy array
    segments = None
    try:
        segments_gen, _ = model.transcribe(
            audio_path,
            beam_size=5,
            word_timestamps=True,
        )
        segments = list(segments_gen)
    except Exception as err:
        logger.warning(f"Default faster-whisper audio decoding failed ({err}). Attempting NumPy waveform fallback...")
        waveform = load_audio_waveform(audio_path)
        if waveform is not None:
            segments_gen, _ = model.transcribe(
                waveform,
                beam_size=5,
                word_timestamps=True,
            )
            segments = list(segments_gen)
        else:
            raise err

    formatted_lines: List[str] = []
    word_segments: List[WordSegment] = []

    for seg in segments:
        abs_start = seg.start + offset_seconds
        abs_end = seg.end + offset_seconds

        start_min = int(abs_start // 60)
        start_sec = int(abs_start % 60)
        formatted_lines.append(f"[{start_min}:{start_sec:02d}] {seg.text.strip()}")

        if seg.words:
            for w in seg.words:
                clean_w = w.word.strip()
                if clean_w:
                    w_abs_start = round(w.start + offset_seconds, 2)
                    w_abs_end = round(w.end + offset_seconds, 2)
                    word_segments.append(WordSegment(word=clean_w, start=w_abs_start, end=w_abs_end))

    del model
    logger.info(f"Transcription complete: {len(formatted_lines)} segment(s), {len(word_segments)} word token(s).")
    return "\n".join(formatted_lines), word_segments
