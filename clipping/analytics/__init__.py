"""
Analytics and performance tracking package for YouTube Shorts:
- SQLite performance database
- Revenue and RPM estimation
- Automated statistics polling
"""

from clipping.analytics.database import AnalyticsDB
from clipping.analytics.revenue_estimator import estimate_revenue
from clipping.analytics.performance_tracker import PerformanceTracker

__all__ = ["AnalyticsDB", "estimate_revenue", "PerformanceTracker"]
