"""
A/B Test Evaluator: Compares Title Variant A (Curiosity Gap) vs. Title Variant B (Direct Value).
"""

import logging
from typing import Dict, Any
from clipping.analytics.database import AnalyticsDB

logger = logging.getLogger("clipping.strategy.ab_tester")


def evaluate_ab_test(db: AnalyticsDB = None) -> Dict[str, Any]:
    """
    Compares average views, likes, and engagement rates across Title Variant A vs B.
    """
    db = db or AnalyticsDB()
    comparison = db.get_variant_comparison()

    res = {
        "variant_a": comparison.get("A", {"count": 0, "avg_views": 0, "avg_likes": 0}),
        "variant_b": comparison.get("B", {"count": 0, "avg_views": 0, "avg_likes": 0}),
        "winner": "TIE_OR_INSUFFICIENT_DATA",
        "margin_percent": 0.0,
    }

    a_views = res["variant_a"].get("avg_views") or 0.0
    b_views = res["variant_b"].get("avg_views") or 0.0
    a_count = res["variant_a"].get("count") or 0
    b_count = res["variant_b"].get("count") or 0

    if a_count >= 3 and b_count >= 3 and max(a_views, b_views) > 0:
        diff = a_views - b_views
        margin = abs(diff) / max(a_views, b_views) * 100.0
        res["margin_percent"] = round(margin, 1)

        if margin >= 10.0:
            if a_views > b_views:
                res["winner"] = "VARIANT_A_CURIOSITY_GAP"
            else:
                res["winner"] = "VARIANT_B_DIRECT_VALUE"

    logger.info(f"A/B Test Status: {res['winner']} (Margin: {res['margin_percent']}%)")
    return res
