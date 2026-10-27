"""
Weekly Performance & Monetization Report Generator.
Summarizes views, subscriber growth velocity, affiliate estimates, and strategy adjustments.
"""

from datetime import datetime
from typing import Dict, Any
from clipping.analytics.database import AnalyticsDB
from clipping.strategy.optimizer import StrategyOptimizer


def generate_weekly_report(db: AnalyticsDB = None) -> str:
    """
    Produces a Markdown-formatted weekly audit report.
    """
    db = db or AnalyticsDB()
    summary = db.get_summary()
    optimizer = StrategyOptimizer(db)
    rec = optimizer.generate_recommendations()
    clips = db.get_all_clips()

    date_str = datetime.now().strftime("%Y-%m-%d")

    report = f"""# YouTube Shorts Monetization Audit ({date_str})

## Executive Summary
- **Total Published Shorts**: {summary['total_clips']}
- **Total Tracked Views**: {summary['total_views']:,}
- **Total Audience Likes**: {summary['total_likes']:,}
- **Total Community Comments**: {summary['total_comments']:,}
- **Estimated Revenue (AdSense + Day-1 Affiliates)**: ${summary['total_revenue']:,.2f}

## Strategic Feedback & Optimization
- **Winning Title Pattern**: {rec.get('title_strategy')}
- **Target Clip Duration**: {rec.get('recommended_clip_duration')} seconds
- **Top Source Channels**: {', '.join(rec.get('top_source_channels', [])) or 'Pending data'}

### Algorithmic Insights:
"""
    for ins in rec.get("insights", []):
        report += f"- {ins}\n"

    report += "\n## Recent Published Shorts Log\n"
    if clips:
        report += "| Date | Title | Duration | Views | Est. Rev |\n"
        report += "| :--- | :--- | :--- | :--- | :--- |\n"
        for c in clips[:10]:
            report += f"| {c['uploaded_at'][:10]} | {c['title'][:40]}... | {c['clip_duration']:.0f}s | {c['views_24h']:,} | ${c['estimated_revenue']:.2f} |\n"
    else:
        report += "_No clips published yet. Run `python -m clipping.clipper` to start._\n"

    return report
