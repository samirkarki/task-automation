"""
Universal publishing package for YouTube, Instagram, and TikTok.
"""

from common.publishing.youtube_uploader import upload_short_to_youtube
from common.publishing.instagram_uploader import upload_reel_to_instagram
from common.publishing.tiktok_uploader import upload_video_to_tiktok
from common.publishing.multi_publisher import publish_to_all_platforms

__all__ = [
    "upload_short_to_youtube",
    "upload_reel_to_instagram",
    "upload_video_to_tiktok",
    "publish_to_all_platforms",
]
