"""
Extraction package: Heatmap peak detection, Whisper word-level transcription, and LLM viral selection.
"""

from clipping.extraction.heatmap import fetch_heatmap, find_peak_windows
from clipping.extraction.transcriber import transcribe_audio
from clipping.extraction.clip_selector import select_viral_clips

__all__ = ["fetch_heatmap", "find_peak_windows", "transcribe_audio", "select_viral_clips"]
