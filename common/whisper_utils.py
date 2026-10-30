#!/usr/bin/env python3
"""
Unified Whisper Transcription Utilities
Ensures cross-platform ffmpeg discovery and extracts millisecond word-level timestamps.
"""

import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Globally disable cuDNN right after importing PyTorch to prevent CUDNN_STATUS_NOT_INITIALIZED
import torch
torch.backends.cudnn.enabled = False

from common.env_loader import load_project_env

load_project_env()

logger = logging.getLogger("common.whisper_utils")

DEFAULT_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
DEFAULT_DEVICE = os.getenv("WHISPER_DEVICE", "cuda")


def ensure_ffmpeg_on_path() -> Optional[str]:
    """Ensures ffmpeg executable is available on system PATH, leveraging imageio_ffmpeg if needed."""
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")

    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        target_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        target_ffmpeg = os.path.join(ffmpeg_dir, target_name)

        if not os.path.exists(target_ffmpeg) and os.path.exists(ffmpeg_exe):
            shutil.copyfile(ffmpeg_exe, target_ffmpeg)

        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

        return target_ffmpeg if os.path.exists(target_ffmpeg) else ffmpeg_exe
    except Exception as e:
        logger.warning(f"Could not auto-configure ffmpeg via imageio_ffmpeg: {e}")
        return None


# Run ffmpeg verification on module import
ensure_ffmpeg_on_path()


def transcribe_audio_words(
    audio_path: Union[str, Path],
    output_json_path: Optional[Union[str, Path]] = None,
    model_size: Optional[str] = None,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Transcribes audio file using OpenAI Whisper with word_timestamps=True.
    Optionally exports strictly to output_json_path.
    Verifies audio transcription model initializes properly on cuda (with cuDNN disabled),
    falling back gracefully to cpu if CUDA allocation, convolution, or feature extraction fails.
    """
    import torch
    import whisper

    torch.backends.cudnn.enabled = False
    ensure_ffmpeg_on_path()

    m_size = model_size or DEFAULT_MODEL_SIZE
    dev = device or (DEFAULT_DEVICE if torch.cuda.is_available() else "cpu")

    model = None
    result = None

    if dev.startswith("cuda"):
        try:
            logger.info(f"Loading Whisper '{m_size}' model on device='{dev}' (cuDNN disabled)...")
            model = whisper.load_model(m_size, device=dev)
            logger.info(f"Transcribing '{audio_path}' with word_timestamps=True on device='{dev}'...")
            result = model.transcribe(str(audio_path), word_timestamps=True)
        except Exception as cuda_err:
            logger.warning(
                f"Whisper CUDA execution failed on '{dev}' ({cuda_err}). "
                "Gracefully falling back to device='cpu'..."
            )
            if model is not None:
                del model
                model = None
            if torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass
            dev = "cpu"

    if result is None:
        logger.info(f"Loading Whisper '{m_size}' model on device='cpu'...")
        model = whisper.load_model(m_size, device="cpu")
        logger.info(f"Transcribing '{audio_path}' with word_timestamps=True on device='cpu'...")
        result = model.transcribe(str(audio_path), word_timestamps=True)

    if output_json_path:
        out_p = Path(output_json_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Subtitles JSON saved to: {out_p}")

    return result
