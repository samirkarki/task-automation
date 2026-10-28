"""
Autonomous 24/7 Scheduler Daemon for YouTube Shorts.
Executes 3 uploads per day at optimal US prime-time viewing hours,
polls live performance metrics every 6 hours, and runs weekly strategy optimization.
"""

import argparse
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import schedule

from clipping.config import UPLOAD_TIMES_UTC
from clipping.orchestrator import run_pipeline
from clipping.analytics.performance_tracker import PerformanceTracker
from clipping.strategy.optimizer import StrategyOptimizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [SHORTS-DAEMON] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("clipping_daemon")

IS_RUNNING = True


def handle_shutdown(signum, frame):
    global IS_RUNNING
    logger.info("Termination signal received. Gracefully shutting down shorts daemon...")
    IS_RUNNING = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def job_publish_short(privacy: str = "public", audio_mode: str = "original", voice: str = "andrew"):
    logger.info(f">>> EXECUTING SCHEDULED SHORT CLIP & PUBLISH JOB (privacy={privacy}, audio_mode={audio_mode}) <<<")
    try:
        run_pipeline(
            mode="auto",
            clips_to_generate=1,
            privacy=privacy,
            audio_mode=audio_mode,
            voice=voice,
        )
    except Exception as e:
        logger.error(f"Error in scheduled shorts job: {e}", exc_info=True)


def job_poll_analytics():
    logger.info(">>> POLLING YOUTUBE PERFORMANCE METRICS <<<")
    try:
        tracker = PerformanceTracker()
        tracker.poll_all_clips()
    except Exception as e:
        logger.error(f"Error polling analytics: {e}")


def job_weekly_optimization():
    logger.info(">>> RUNNING WEEKLY STRATEGY OPTIMIZATION <<<")
    try:
        optimizer = StrategyOptimizer()
        rec = optimizer.generate_recommendations()
        logger.info(f"Weekly optimization applied: {rec}")
    except Exception as e:
        logger.error(f"Error in weekly optimization: {e}")


def format_time_until(target_dt: datetime) -> str:
    now = datetime.now()
    diff = target_dt - now
    total_seconds = max(0, int(diff.total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    return f"{hours}h {minutes}m"


def start_daemon(privacy: str = "public", audio_mode: str = "original", voice: str = "andrew", run_now: bool = False):
    logger.info("=================================================================")
    logger.info("Starting Autonomous YouTube Shorts Daemon")
    logger.info(f"Scheduled Upload Times (UTC): {', '.join(UPLOAD_TIMES_UTC)}")
    logger.info(f"Settings -> Privacy: {privacy} | Audio: {audio_mode} | Voice: {voice}")
    logger.info("Analytics Polling: Every 6 hours")
    logger.info("Weekly Optimization: Every Monday at 00:00 UTC")
    logger.info("=================================================================")

    # Register upload schedule
    for t_str in UPLOAD_TIMES_UTC:
        schedule.every().day.at(t_str).do(
            job_publish_short,
            privacy=privacy,
            audio_mode=audio_mode,
            voice=voice,
        )

    # Register analytics polling every 6 hours
    schedule.every(6).hours.do(job_poll_analytics)

    # Register weekly strategy optimization
    schedule.every().monday.at("00:00").do(job_weekly_optimization)

    if run_now:
        logger.info("[--run-now] Triggering immediate clip & upload job before entering scheduled loop...")
        job_publish_short(privacy=privacy, audio_mode=audio_mode, voice=voice)

    next_job = schedule.next_run()
    if next_job:
        logger.info(f"Next scheduled job at: {next_job.strftime('%Y-%m-%d %H:%M:%S')} (in {format_time_until(next_job)}). Daemon is active and waiting in background...")

    last_heartbeat = time.time()
    while IS_RUNNING:
        schedule.run_pending()
        time.sleep(20)

        # Log a heartbeat every 60 minutes
        if time.time() - last_heartbeat >= 3600:
            last_heartbeat = time.time()
            next_j = schedule.next_run()
            eta_str = format_time_until(next_j) if next_j else "N/A"
            logger.info(f"[Heartbeat] Shorts daemon active. Next run at: {next_j} (in {eta_str}).")

    logger.info("Shorts daemon terminated.")


def main():
    parser = argparse.ArgumentParser(description="Autonomous 24/7 Scheduler Daemon for YouTube Shorts")
    parser.add_argument("--privacy", type=str, default="public", choices=["public", "unlisted", "private"], help="YouTube upload privacy status (default: public).")
    parser.add_argument("--audio-mode", type=str, default="original", choices=["original", "soothing"], help="Audio mode: 'original' (keeps real speaker's human voice) or 'soothing' (uses natural human voiceover).")
    parser.add_argument("--voice", type=str, default="andrew", choices=["andrew", "brian", "christopher", "ava", "ryan"], help="Soothing human voice preset (default: andrew).")
    parser.add_argument("--run-now", action="store_true", help="Immediately execute one clip & upload run right now upon starting, before waiting for the scheduled slots.")

    args = parser.parse_args()
    start_daemon(
        privacy=args.privacy,
        audio_mode=args.audio_mode,
        voice=args.voice,
        run_now=args.run_now,
    )


if __name__ == "__main__":
    main()
