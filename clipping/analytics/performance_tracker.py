"""
Performance Tracker: Polls YouTube Data API v3 for views, likes, and comment counts.
Consumes minimal API quota (1 unit per batch of up to 50 videos).
"""

from datetime import datetime, timezone
import logging
from typing import List, Dict, Any

from clipping.analytics.database import AnalyticsDB
from clipping.analytics.revenue_estimator import estimate_revenue
from clipping.publishing.youtube_uploader import get_authenticated_service

logger = logging.getLogger("clipping.analytics.performance_tracker")


class PerformanceTracker:
    def __init__(self, db: AnalyticsDB = None):
        self.db = db or AnalyticsDB()

    def poll_all_clips(self) -> int:
        """
        Polls statistics for all published clips in the database and updates metrics.
        Returns the number of clips updated.
        """
        clips = self.db.get_all_clips()
        if not clips:
            logger.info("No clips in database to poll.")
            return 0

        # Filter out dry-run or simulated IDs
        real_clips = [c for c in clips if not c["video_id"].startswith("DRY_RUN") and not c["video_id"].startswith("SIMULATED")]
        if not real_clips:
            logger.info(f"Database contains {len(clips)} clip(s), but all are dry-run / simulated.")
            return 0

        service = get_authenticated_service()
        if not service:
            logger.warning("YouTube API service unavailable. Cannot poll live statistics.")
            return 0

        # Batch in chunks of 50 (max YouTube Data API allows per call = 1 quota unit)
        updated_count = 0
        for i in range(0, len(real_clips), 50):
            batch = real_clips[i : i + 50]
            ids_str = ",".join([c["video_id"] for c in batch])

            try:
                resp = service.videos().list(part="statistics", id=ids_str).execute()
                items = resp.get("items", [])

                for item in items:
                    v_id = item["id"]
                    stats = item.get("statistics", {})
                    views = int(stats.get("viewCount", 0))
                    likes = int(stats.get("likeCount", 0))
                    comments = int(stats.get("commentCount", 0))

                    rev = estimate_revenue(views)
                    self.db.update_metrics(
                        video_id=v_id,
                        views=views,
                        likes=likes,
                        comments=comments,
                        estimated_revenue=rev["total_estimated"],
                    )
                    updated_count += 1
            except Exception as e:
                logger.warning(f"Error querying statistics batch: {e}")

        logger.info(f"Updated live performance metrics for {updated_count} clip(s).")
        return updated_count
