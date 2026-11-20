"""
MrBeast Challenges, Stunts & High-Stakes Clips Profile.
"""

from clipping.profiles.base import ClipProfile

MRBEAST_PROFILE = ClipProfile(
    name="mrbeast",
    display_name="MrBeast Challenges & Stunts",
    category_id="24",  # Entertainment
    search_keywords=[
        "MrBeast challenge insane climax",
        "MrBeast $1000000 winner moment",
        "MrBeast crazy stunt reaction",
        "MrBeast elimination tense moment",
        "MrBeast survival challenge ending",
    ],
    channel_whitelist=[
        "MrBeast",
        "Beast Reacts",
        "MrBeast 2",
        "MrBeast Gaming",
    ],
    layout_mode="action_crop",
    facecam_position=None,
    split_ratio=0.0,
    min_clip_duration=22.0,
    max_clip_duration=58.0,
    optimal_clip_duration=42.0,
    duck_background_music=False,
    punch_in_on_loudness=True,
    loudness_spike_db=7.0,
    subtitle_style={
        "font_family": "Komika Axis, Arial Black, Impact",
        "font_size": 56,
        "primary_color": "&H0000FFFF",  # Bright Yellow in BGR/ASS
        "secondary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 5.0,
        "shadow_depth": 3.0,
        "animation": "pop",
        "vertical_margin": 680,
    },
    target_tags=[
        "MrBeast", "MrBeastChallenge", "MrBeastShorts", "InsaneChallenge",
        "ViralShorts", "Trending", "Shorts"
    ],
    description_template="""{summary}

🔥 The craziest MrBeast moments & challenge climaxes!
Subscribe for daily viral challenge highlights.

Original Video by MrBeast ({original_creator})
#MrBeast #Challenge #Viral #Shorts""",
    pinned_comment_template="""😱 Would YOU survive this challenge for $1,000,000? Comment below! 👇""",
    estimated_rpm=0.50,
)
