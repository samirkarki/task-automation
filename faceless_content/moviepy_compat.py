#!/usr/bin/env python3
"""
MoviePy v1 and v2 Cross-Compatibility Layer
Abstracts away the breaking changes between MoviePy 1.x (moviepy.editor)
and MoviePy 2.x (moviepy top-level package and renamed property setters).
"""

import logging
from typing import Any, Tuple, Union

logger = logging.getLogger("moviepy_compat")

# Try MoviePy v1.x import style first, fallback to MoviePy v2.x
MOVIEPY_AVAILABLE = False
MOVIEPY_VERSION = 0

try:
    from moviepy.editor import (
        AudioFileClip,
        VideoClip,
        ImageClip,
        CompositeVideoClip,
        CompositeAudioClip,
    )
    MOVIEPY_AVAILABLE = True
    MOVIEPY_VERSION = 1
except ImportError:
    try:
        from moviepy import (
            AudioFileClip,
            VideoClip,
            ImageClip,
            CompositeVideoClip,
        )
        try:
            from moviepy import CompositeAudioClip
        except ImportError:
            from moviepy.audio.AudioClip import CompositeAudioClip
        MOVIEPY_AVAILABLE = True
        MOVIEPY_VERSION = 2
    except ImportError:
        AudioFileClip = None
        VideoClip = None
        ImageClip = None
        CompositeVideoClip = None
        CompositeAudioClip = None
        MOVIEPY_AVAILABLE = False
        MOVIEPY_VERSION = 0


def is_moviepy_available() -> bool:
    """Returns True if MoviePy is installed and can be imported."""
    return MOVIEPY_AVAILABLE


def set_clip_duration(clip: Any, duration: float) -> Any:
    """Compatibility wrapper for clip duration setter (v1: set_duration, v2: with_duration)."""
    if clip is None:
        return None
    if hasattr(clip, "with_duration"):
        return clip.with_duration(duration)
    if hasattr(clip, "set_duration"):
        return clip.set_duration(duration)
    return clip


def set_clip_fps(clip: Any, fps: Union[int, float]) -> Any:
    """Compatibility wrapper for clip fps setter (v1: set_fps, v2: with_fps)."""
    if clip is None:
        return None
    if hasattr(clip, "with_fps"):
        return clip.with_fps(fps)
    if hasattr(clip, "set_fps"):
        return clip.set_fps(fps)
    return clip


def set_clip_start(clip: Any, start_time: float) -> Any:
    """Compatibility wrapper for clip start time (v1: set_start, v2: with_start)."""
    if clip is None:
        return None
    if hasattr(clip, "with_start"):
        return clip.with_start(start_time)
    if hasattr(clip, "set_start"):
        return clip.set_start(start_time)
    return clip


def set_clip_position(clip: Any, position: Union[str, Tuple[Any, Any]]) -> Any:
    """Compatibility wrapper for clip position (v1: set_position, v2: with_position)."""
    if clip is None:
        return None
    if hasattr(clip, "with_position"):
        return clip.with_position(position)
    if hasattr(clip, "set_position"):
        return clip.set_position(position)
    return clip


def set_clip_audio(clip: Any, audio_clip: Any) -> Any:
    """Compatibility wrapper for attaching audio (v1: set_audio, v2: with_audio)."""
    if clip is None:
        return None
    if hasattr(clip, "with_audio"):
        return clip.with_audio(audio_clip)
    if hasattr(clip, "set_audio"):
        return clip.set_audio(audio_clip)
    return clip


def scale_clip_volume(clip: Any, factor: float) -> Any:
    """Compatibility wrapper for audio volume adjustment (v1: volumex, v2: with_volume_scaled / MultiplyVolume)."""
    if clip is None:
        return None
    if hasattr(clip, "with_volume_scaled"):
        return clip.with_volume_scaled(factor)
    if hasattr(clip, "volumex"):
        return clip.volumex(factor)
    try:
        from moviepy.audio.fx import MultiplyVolume
        return clip.with_effects([MultiplyVolume(factor)])
    except Exception:
        pass
    return clip
