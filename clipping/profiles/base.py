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
    # Long-form compilation settings
    output_format: str = "shorts"               # "shorts" | "longform" | "both"
    longform_duration: float = 480.0            # target duration in seconds (default 8 min)
    # Channel branding
    channel_brand_name: str = "ClipBot"         # your own channel name on bumpers/badges
    attribution_avatar_path: Optional[str] = None  # path to avatar PNG/JPEG or None
    show_attribution_badge: bool = True         # badge in no-facecam Shorts
    mute_game_music: bool = False               # auto-mute game music in long-form
