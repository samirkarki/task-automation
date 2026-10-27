"""
Publishing package for YouTube Shorts:
- SEO metadata optimizer (LLM-driven title A/B variants & descriptions)
- Affiliate & Bridge-Page injector for day-1 monetization
- Resumable YouTube Data API v3 uploader with OAuth2
"""

from clipping.publishing.metadata_optimizer import generate_metadata
from clipping.publishing.affiliate_injector import inject_monetization_links
from clipping.publishing.youtube_uploader import upload_short_to_youtube

__all__ = [
    "generate_metadata",
    "inject_monetization_links",
    "upload_short_to_youtube",
]
