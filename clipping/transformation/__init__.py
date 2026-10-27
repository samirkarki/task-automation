"""
Transformation package implementing the 6-layer transformative shield:
- Commentary writer (LLM)
- TTS narrator (neural voice)
- Subtitle styler (ASS karaoke)
- Audio mixer (replaces source audio with master track)
- Video processor (FFmpeg 9:16 vertical render)
"""

from clipping.transformation.commentary_writer import write_commentary
from clipping.transformation.tts_narrator import generate_narration
from clipping.transformation.subtitle_styler import generate_karaoke_subtitles
from clipping.transformation.audio_mixer import compose_clip_audio
from clipping.transformation.video_processor import render_transformed_short

__all__ = [
    "write_commentary",
    "generate_narration",
    "generate_karaoke_subtitles",
    "compose_clip_audio",
    "render_transformed_short",
]
