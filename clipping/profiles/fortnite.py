"""
Fortnite Clutch Plays & Streamer Moments Profile.
"""

from clipping.profiles.base import ClipProfile

FORTNITE_PROFILE = ClipProfile(
    name="game-fortnite",
    display_name="Fortnite Highlights & Clutch Moments",
    category_id="20",  # Gaming
    search_keywords=[
        "Fortnite insane clutch stream",
        "Fortnite funny streamer rage",
        "Fortnite tournament winning moment",
        "Fortnite unreal play livestream",
        "Fortnite new season glitch reaction",
        "Fortnite streamer 1v4 clutch",
    ],
    channel_whitelist=[
        "Ninja",
        "SypherPK",
        "Mongraal",
        "Clix",
        "NickEh30",
        "Buce",
    ],
    layout_mode="smart_split_screen",
    facecam_position="top",
    split_ratio=0.35,
    min_clip_duration=18.0,
    max_clip_duration=55.0,
    optimal_clip_duration=35.0,
    duck_background_music=True,
    punch_in_on_loudness=True,
    loudness_spike_db=8.5,
    subtitle_style={
        "font_family": "Montserrat ExtraBold, Arial Black, Impact",
        "font_size": 52,
        "primary_color": "&H00FFFF00",  # Bright Cyan in BGR/ASS
        "secondary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 4.5,
        "shadow_depth": 2.5,
        "animation": "bounce",
        "vertical_margin": 640,
    },
    target_tags=[
        "Fortnite", "FortniteClips", "FortniteHighlights", "GamingShorts",
        "FortniteMontage", "ClutchPlay", "StreamerMoments", "Shorts"
    ],
    description_template="""{summary}

🏆 Insane Fortnite clutch plays, tournament highlights, and streamer moments!
Subscribe for daily Fortnite clips.

Original Creator: {original_creator}
#Fortnite #FortniteClips #Gaming #Shorts""",
    pinned_comment_template="""🔥 Was this a 200 IQ play or pure luck? Tell us below! 👇""",
    estimated_rpm=0.35,
)
