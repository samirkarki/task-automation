#!/usr/bin/env python3
"""
Autonomous Multi-Profile YouTube Shorts Clipper, Publisher & Monetization Engine.
CLI Entry Point.

Usage:
    python -m clipping.clipper --profile game-gta6           # Full autonomous GTA6 discovery, split-screen clip & publish
    python -m clipping.clipper --profile mrbeast --url <URL> # Clip specific MrBeast challenge video with action tracking
    python -m clipping.clipper --list-profiles               # List available niche profiles
    python -m clipping.clipper --dry-run                     # Test full pipeline without live YouTube upload
    python -m clipping.clipper --report                      # Print weekly performance audit report
    python -m clipping.clipper --optimize                    # Run strategy optimizer feedback analysis
    python -m clipping.clipper --poll                        # Poll live view counts from YouTube Data API
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
from clipping.profiles import list_profiles, get_profile
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
    parser = argparse.ArgumentParser(description="Autonomous Multi-Profile YouTube Shorts Monetization Engine")
    parser.add_argument(
        "--profile",
        type=str,
        default="game-gta6",
        help="Target profile: game-gta6 (default), game-fortnite, mrbeast, business",
    )
    parser.add_argument("--list-profiles", action="store_true", help="List all registered content profiles and exit.")
    parser.add_argument("--url", type=str, default=None, help="Target specific YouTube video URL.")
    parser.add_argument("--mode", type=str, default="auto", choices=["auto", "url"], help="Execution mode.")
    parser.add_argument("--dry-run", action="store_true", help="Execute pipeline without publishing live to YouTube.")
    parser.add_argument("--clips", type=int, default=3, help="Number of clips to generate.")
    parser.add_argument("--privacy", type=str, default="public", choices=["public", "unlisted", "private"], help="YouTube upload privacy status (default: public).")
    parser.add_argument("--audio-mode", type=str, default="original", choices=["original", "soothing"], help="Audio mode: 'original' (keeps real speaker's human voice) or 'soothing' (uses natural human voiceover).")
    parser.add_argument("--voice", type=str, default="andrew", choices=["andrew", "brian", "christopher", "ava", "ryan"], help="Soothing human voice preset (default: andrew).")
    parser.add_argument(
        "--output-format",
        type=str,
        default=None,
        choices=["shorts", "longform", "both"],
        help=(
            "Override profile output format: "
            "'shorts' (Shorts only), "
            "'longform' (10-min compilation only), "
            "'both' (Shorts + compilation, default for GTA6)."
        ),
    )
    parser.add_argument("--report", action="store_true", help="Generate and print weekly performance audit report.")
    parser.add_argument("--optimize", action="store_true", help="Run strategy optimizer feedback loop.")
    parser.add_argument("--poll", action="store_true", help="Poll YouTube Data API for live statistics.")
    parser.add_argument("--auth", action="store_true", help="Authenticate YouTube in headless Ubuntu terminal without browser.")
    parser.add_argument("--auth-instagram", action="store_true", help="Authenticate Instagram Graph API in headless Ubuntu terminal.")

    args = parser.parse_args()

    if args.list_profiles:
        print("\nRegistered Clipping Profiles:")
        for p_name in list_profiles():
            prof = get_profile(p_name)
            print(f"  • {prof.name:<15} -> {prof.display_name} (Layout: {prof.layout_mode})")
        print()
        return

    # Route special commands
    if args.auth:
        from clipping.auth import authenticate_headless
        authenticate_headless()
        return
    if args.auth_instagram:
        from clipping.auth_instagram import authenticate_instagram
        authenticate_instagram()
        return
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

    # Default: Run clipping pipeline with selected profile
    mode = "url" if args.url else args.mode
    run_pipeline(
        mode=mode,
        url=args.url,
        dry_run=args.dry_run,
        clips_to_generate=args.clips,
        privacy=args.privacy,
        audio_mode=args.audio_mode,
        voice=args.voice,
        profile_name=args.profile,
        output_format_override=args.output_format,
    )


if __name__ == "__main__":
    main()
