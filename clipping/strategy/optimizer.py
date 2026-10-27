"""
Strategy Optimizer: Closes the feedback loop by mining performance records
and auto-adjusting selection weights, hook preferences, and pacing.
"""

import logging
from typing import Dict, Any
from clipping.analytics.database import AnalyticsDB
from clipping.strategy.ab_tester import evaluate_ab_test

logger = logging.getLogger("clipping.strategy.optimizer")


class StrategyOptimizer:
    def __init__(self, db: AnalyticsDB = None):
        self.db = db or AnalyticsDB()

    def generate_recommendations(self) -> Dict[str, Any]:
        """
        Mines performance data and produces actionable algorithmic recommendations.
        """
        ab_results = evaluate_ab_test(self.db)
        clips = self.db.get_all_clips()

        rec = {
            "title_strategy": ab_results.get("winner", "INSUFFICIENT_DATA"),
            "recommended_clip_duration": 40.0,
            "top_source_channels": [],
            "insights": [],
        }

        if not clips:
            rec["insights"].append("No published clips recorded yet. Continue initial upload schedule.")
            return rec

        # Analyze duration brackets (Short: <35s, Medium: 35-45s, Long: >45s)
        durations = [c.get("clip_duration", 40.0) for c in clips]
        avg_dur = sum(durations) / len(durations) if durations else 40.0
        rec["recommended_clip_duration"] = round(avg_dur, 1)

        # Count top channels
        channel_counts = {}
        for c in clips:
            ch = c.get("source_channel", "Unknown")
            channel_counts[ch] = channel_counts.get(ch, 0) + 1

        rec["top_source_channels"] = sorted(channel_counts.keys(), key=lambda k: channel_counts[k], reverse=True)[:5]

        if ab_results.get("winner") == "VARIANT_A_CURIOSITY_GAP":
            rec["insights"].append("Curiosity-gap hooks are outperforming direct value. Prioritize 'Why...' and 'The secret...' formats.")
        elif ab_results.get("winner") == "VARIANT_B_DIRECT_VALUE":
            rec["insights"].append("Direct-value hooks are winning. Prioritize 'How to...' and framework numbered lists.")
        else:
            rec["insights"].append("A/B variant test running. Maintain 50/50 split across upload schedule.")

        logger.info(f"Strategy Optimizer recommendations: {rec['insights']}")
        return rec
