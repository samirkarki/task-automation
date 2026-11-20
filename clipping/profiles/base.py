"""
Base profile definitions for the Multi-Profile Clipping Engine.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ClipProfile:
    name: str
    display_name: str
    category_id: str
    search_keywords: List[str]
    channel_whitelist: List[str]
    layout_mode: str  # "smart_split_screen" | "action_crop" | "single_speaker"
    facecam_position: Optional[str] = "top"  # "top" | "pip" | None
    split_ratio: float = 0.35               # e.g., 35% facecam top, 65% gameplay bottom
    min_clip_duration: float = 18.0
    max_clip_duration: float = 58.0
    optimal_clip_duration: float = 40.0
    duck_background_music: bool = True
    punch_in_on_loudness: bool = True
    loudness_spike_db: float = 8.0          # dB above average to trigger punch-in
    subtitle_style: Dict[str, Any] = field(default_factory=dict)
    target_tags: List[str] = field(default_factory=list)
    description_template: str = ""
    pinned_comment_template: str = ""
    estimated_rpm: float = 0.35
