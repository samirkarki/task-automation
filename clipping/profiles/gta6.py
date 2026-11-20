"""
GTA6 Streamer & Gameplay Highlights Profile.
"""

from clipping.profiles.base import ClipProfile

GTA6_PROFILE = ClipProfile(
    name="game-gta6",
    display_name="Grand Theft Auto VI Highlights",
    category_id="20",  # Gaming
    search_keywords=[
        "GTA 6 funny moments streamer",
        "GTA 6 gameplay fails livestream",
        "GTA 6 insane police chase",
        "GTA 6 easter eggs and secrets",
        "GTA 6 streamer reaction funny",
        "GTA 6 crazy physics glitch",
        "GTA 6 best moments stream",
        "GTA 6 mission gameplay reaction",
    ],
    channel_whitelist=[
        "xQc",
        "Kai Cenat",
        "shroud",
        "Jynxzi",
        "IShowSpeed",
        "Tarik",
        "SypherPK",
        "Tfue",
    ],
    layout_mode="smart_split_screen",
    facecam_position="top",
    split_ratio=0.36,  # 36% top facecam, 64% bottom gameplay
    min_clip_duration=18.0,
    max_clip_duration=58.0,
    optimal_clip_duration=38.0,
    duck_background_music=True,
    punch_in_on_loudness=True,
    loudness_spike_db=9.0,
    subtitle_style={
        "font_family": "Montserrat ExtraBold, Arial Black, Impact",
        "font_size": 52,
        "primary_color": "&H0000FFFF",  # Bright Yellow in BGR/ASS
        "secondary_color": "&H00FFFFFF", # White
        "outline_color": "&H00000000",   # Solid Black Outline
        "outline_width": 4.5,
        "shadow_depth": 2.5,
        "animation": "bounce",
        "vertical_margin": 640,
    },
    target_tags=[
        "GTA6", "GTA6Gameplay", "GTA6Leaks", "GTA6Trailer", "GrandTheftAuto6",
        "GamingShorts", "StreamerMoments", "FunnyGaming", "GTAClips", "Shorts"
    ],
    description_template="""{summary}

🎮 Best GTA 6 moments, gameplay fails & streamer reactions!
Subscribe for daily GTA 6 clips and highlights.

Original Streamer: {original_creator}
Content analyzed and shared under transformative fair-use commentary.
#GTA6 #GrandTheftAuto6 #Gaming #Shorts #StreamerMoments""",
    pinned_comment_template="""💀 What's YOUR rating of this GTA 6 moment? (1-10) Drop it below 👇

🔔 Subscribe for daily GTA 6 gameplay & stream highlights!""",
    estimated_rpm=0.45,
)
