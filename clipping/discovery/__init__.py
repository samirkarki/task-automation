"""
Discovery and Compliance package for YouTube Shorts automation.
"""

from clipping.discovery.searcher import search_niche_videos
from clipping.discovery.velocity_ranker import rank_by_velocity
from clipping.discovery.compliance_filter import ComplianceFilter

__all__ = ["search_niche_videos", "rank_by_velocity", "ComplianceFilter"]
