"""
Revenue Estimator: Computes projected earnings based on view counts,
niche RPM baselines, and estimated bridge-page affiliate conversion rates.
"""

from typing import Dict, Any
from clipping.config import NICHE_CONFIG


def estimate_revenue(
    views: int,
    rpm: float = None,
    affiliate_conversion_rate: float = 0.0008,  # ~8 conversions per 10,000 views
    avg_affiliate_payout: float = 25.0,        # Average SaaS / Broker / Book commission
) -> Dict[str, float]:
    """
    Calculates:
    1. ad_revenue: views * RPM / 1000
    2. affiliate_revenue: views * conversion_rate * avg_commission
    3. total_estimated_revenue: ad_revenue + affiliate_revenue
    """
    active_rpm = rpm or NICHE_CONFIG.get("estimated_rpm", 0.20)

    # 1. Shorts AdSense pool payout
    ad_revenue = (views / 1000.0) * active_rpm

    # 2. Bridge page affiliate earnings (active from Day 1)
    est_conversions = views * affiliate_conversion_rate
    affiliate_revenue = est_conversions * avg_affiliate_payout

    total = ad_revenue + affiliate_revenue

    return {
        "views": views,
        "rpm": active_rpm,
        "ad_revenue": round(ad_revenue, 2),
        "affiliate_revenue": round(affiliate_revenue, 2),
        "total_estimated": round(total, 2),
    }
