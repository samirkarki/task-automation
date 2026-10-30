#!/usr/bin/env python3
"""
Unified Text-to-Speech Engine
Supports:
1. Kokoro TTS (Local high-fidelity neural voices via PyTorch/CUDA or CPU)
2. Edge-TTS (Zero-cost cloud neural voices, supporting Nepali, Hindi, and English)
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Union, List
import numpy as np

# Globally disable cuDNN right after importing PyTorch to prevent CUDNN_STATUS_NOT_INITIALIZED
import torch
torch.backends.cudnn.enabled = False

from common.env_loader import load_project_env

load_project_env()

logger = logging.getLogger("common.tts_engine")


def synthesize_with_kokoro(
    text: str,
    output_path: Union[str, Path],
    voice: str = "af_heart",
    lang_code: str = "a",
    speed: float = 1.0,
    device: Optional[str] = None,
) -> Path:
    """
    Synthesize audio using local Kokoro TTS pipeline.
    Exports 24,000 Hz WAV.
    Allows Kokoro to run on cuda with cuDNN disabled, falling back gracefully
    to device='cpu' if any GPU initialization or runtime error occurs.
    """
    import soundfile as sf
    import torch
    from kokoro import KPipeline

    torch.backends.cudnn.enabled = False

    target_path = Path(output_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    def _run_synthesis(target_dev: str) -> List[np.ndarray]:
        logger.info(f"Synthesizing Kokoro audio (voice='{voice}', lang='{lang_code}', device='{target_dev}')...")
        pipeline = KPipeline(lang_code=lang_code, device=target_dev)
        chunks: List[np.ndarray] = []
        generator = pipeline(text, voice=voice, speed=speed)
        for result in generator:
            if result.output is not None and result.output.audio is not None:
                chunk = result.output.audio
                if isinstance(chunk, torch.Tensor):
                    chunk = chunk.detach().cpu().numpy()
                chunks.append(chunk)

        if not chunks:
            raise RuntimeError("Kokoro TTS did not yield any audio output.")
        return chunks

    audio_chunks: List[np.ndarray] = []
    if device.startswith("cuda"):
        try:
            audio_chunks = _run_synthesis(device)
        except Exception as gpu_err:
            logger.warning(
                f"Kokoro GPU execution failed on '{device}' ({gpu_err}). "
                "Gracefully falling back to device='cpu'..."
            )
            if torch.cuda.is_available():
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass
            audio_chunks = _run_synthesis("cpu")
    else:
        audio_chunks = _run_synthesis(device)

    full_audio = np.concatenate(audio_chunks, axis=0)
    sf.write(str(target_path), full_audio, 24000)
    logger.info(f"Kokoro audio saved: {target_path} ({len(full_audio)/24000:.2f}s)")
    return target_path


async def _synthesize_edge_async(
    text: str,
    output_path: Union[str, Path],
    voice: str = "en-US-ChristopherNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> Path:
    import edge_tts

    target_path = Path(output_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(str(target_path))
    return target_path


def synthesize_with_edge(
    text: str,
    output_path: Union[str, Path],
    voice: str = "en-US-ChristopherNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> Path:
    """Synchronous wrapper for Edge-TTS synthesis."""
    logger.info(f"Synthesizing Edge-TTS audio (voice='{voice}')...")
    return asyncio.run(_synthesize_edge_async(text, output_path, voice, rate, pitch))
