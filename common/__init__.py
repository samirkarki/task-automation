"""
Common utilities and shared core libraries for Task Automation.
Contains cross-cutting concerns:
- env_loader: Universal .env loading across all modules
- moviepy_compat: MoviePy 1.x / 2.x compatibility layer
- ollama_client: Resilient Ollama interaction with model fallbacks & JSON parsing
- tts_engine: Speech synthesis (Kokoro TTS and Edge-TTS)
- whisper_utils: Transcription and word-level timestamps
- stock_media: Stock video & photo providers (Pexels, Pixabay, Wikimedia)
- publishing: Multi-platform publishing to YouTube, TikTok, Instagram
"""

from common.env_loader import load_project_env

__all__ = ["load_project_env"]
