"""
Ranks candidate videos by views-per-day velocity and audience engagement momentum.
"""

from datetime import date
import logging
from typing import List
from clipping.models import VideoMeta

logger = logging.getLogger("clipping.discovery.velocity_ranker")


def rank_by_velocity(
    videos: List[VideoMeta],
    min_views: int = 20000,
    min_velocity: float = 1000.0,
    max_return: int = 15,
) -> List[VideoMeta]:
    """
    Calculates velocity (views per day since upload) and filters out stale or underperforming videos.
    Returns sorted list from highest velocity to lowest.
    """
    today = date.today()
    qualified: List[VideoMeta] = []

    for v in videos:
        days_live = max(1, (today - (v.upload_date or today)).days)
        v.velocity = v.view_count / float(days_live)

        # Allow videos with high views OR high velocity
        if v.view_count >= min_views and v.velocity >= min_velocity:
            qualified.append(v)
        elif v.view_count >= 100000:
            # Established authority content
            qualified.append(v)

    ranked = sorted(qualified, key=lambda x: x.velocity, reverse=True)
    logger.info(f"Filtered {len(videos)} down to {len(ranked)} velocity-qualified videos.")
    return ranked[:max_return]
