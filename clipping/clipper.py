#!/usr/bin/env python3
"""
Autonomous YouTube Shorts Clipper, Publisher & Monetization Engine.
CLI Entry Point.

Usage:
    python -m clipping.clipper                     # Full autonomous discovery, clip & publish
    python -m clipping.clipper --url <URL>         # Clip specific long-form video
    python -m clipping.clipper --dry-run           # Test full pipeline without live YouTube upload
    python -m clipping.clipper --report            # Print weekly performance audit report
    python -m clipping.clipper --optimize          # Run strategy optimizer feedback analysis
    python -m clipping.clipper --poll              # Poll live view counts from YouTube Data API
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from clipping.orchestrator import run_pipeline
from clipping.strategy.weekly_report import generate_weekly_report
from clipping.strategy.optimizer import StrategyOptimizer
from clipping.analytics.performance_tracker import PerformanceTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("clipper")


def main():
    parser = argparse.ArgumentParser(description="Autonomous YouTube Shorts Monetization Engine")
    parser.add_argument("--url", type=str, default=None, help="Target specific YouTube video URL.")
    parser.add_argument("--mode", type=str, default="auto", choices=["auto", "url"], help="Execution mode.")
    parser.add_argument("--dry-run", action="store_true", help="Execute pipeline without publishing live to YouTube.")
    parser.add_argument("--clips", type=int, default=3, help="Number of clips to generate.")
    parser.add_argument("--report", action="store_true", help="Generate and print weekly performance audit report.")
    parser.add_argument("--optimize", action="store_true", help="Run strategy optimizer feedback loop.")
    parser.add_argument("--poll", action="store_true", help="Poll YouTube Data API for live statistics.")

    args = parser.parse_args()

    # Route commands
    if args.report:
        report = generate_weekly_report()
        print("\n" + report)
        return

    if args.optimize:
        optimizer = StrategyOptimizer()
        rec = optimizer.generate_recommendations()
        print("\n=== STRATEGY OPTIMIZER INSIGHTS ===")
        for ins in rec.get("insights", []):
            print(f"• {ins}")
        print(f"Recommended Duration: {rec.get('recommended_clip_duration')}s")
        print(f"Title Strategy: {rec.get('title_strategy')}")
        return

    if args.poll:
        tracker = PerformanceTracker()
        tracker.poll_all_clips()
        return

    # Default: Run clipping pipeline
    mode = "url" if args.url else args.mode
    run_pipeline(
        mode=mode,
        url=args.url,
        dry_run=args.dry_run,
        clips_to_generate=args.clips,
    )


if __name__ == "__main__":
    main()
