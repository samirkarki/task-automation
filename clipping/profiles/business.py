"""
Business & Wealth Mindset Profile (Legacy support).
"""

from clipping.profiles.base import ClipProfile

BUSINESS_PROFILE = ClipProfile(
    name="business",
    display_name="Business & Wealth Mindset",
    category_id="22",  # People & Blogs / Education
    search_keywords=[
        "business advice entrepreneur interview",
        "wealth building strategy podcast",
        "how to make money online mentor",
        "startup founder story advice",
        "financial freedom investing tips",
        "billionaire mindset interview",
        "productivity habits high performance",
        "AI tools business automation",
    ],
    channel_whitelist=[
        "The Diary Of A CEO",
        "My First Million",
        "Andrew Huberman",
        "Lex Fridman",
        "Alex Hormozi",
    ],
    layout_mode="single_speaker",
    facecam_position=None,
    split_ratio=0.0,
    min_clip_duration=28.0,
    max_clip_duration=55.0,
    optimal_clip_duration=40.0,
    duck_background_music=False,
    punch_in_on_loudness=False,
    loudness_spike_db=15.0,
    subtitle_style={
        "font_family": "Arial Black",
        "font_size": 48,
        "primary_color": "&H0000FFFF",
        "secondary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline_width": 3.5,
        "shadow_depth": 2.0,
        "animation": "standard",
        "vertical_margin": 680,
    },
    target_tags=[
        "business", "entrepreneur", "wealth", "money", "investing",
        "startup", "mindset", "motivation", "success", "finance", "Shorts"
    ],
    description_template="""{summary}

Original content by {original_creator} — analyzed for educational commentary.
#Shorts #Business #Entrepreneur #Money #Wealth #Success""",
    pinned_comment_template="""💬 What's YOUR biggest takeaway from this? Drop your thoughts below 👇""",
    estimated_rpm=0.20,
)
