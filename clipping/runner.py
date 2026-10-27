"""
Autonomous 24/7 Scheduler Daemon for YouTube Shorts.
Executes 3 uploads per day at optimal US prime-time viewing hours,
polls live performance metrics every 6 hours, and runs weekly strategy optimization.
"""

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


def job_publish_short():
    logger.info(">>> EXECUTING SCHEDULED SHORT CLIP & PUBLISH JOB <<<")
    try:
        run_pipeline(mode="auto", clips_to_generate=1)
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


def start_daemon():
    logger.info("=================================================================")
    logger.info("Starting Autonomous YouTube Shorts Daemon")
    logger.info(f"Scheduled Upload Times (UTC): {', '.join(UPLOAD_TIMES_UTC)}")
    logger.info("Analytics Polling: Every 6 hours")
    logger.info("Weekly Optimization: Every Monday at 00:00 UTC")
    logger.info("=================================================================")

    # Register upload schedule
    for t_str in UPLOAD_TIMES_UTC:
        schedule.every().day.at(t_str).do(job_publish_short)

    # Register analytics polling every 6 hours
    schedule.every(6).hours.do(job_poll_analytics)

    # Register weekly strategy optimization
    schedule.every().monday.at("00:00").do(job_weekly_optimization)

    while IS_RUNNING:
        schedule.run_pending()
        time.sleep(20)

    logger.info("Shorts daemon terminated.")


if __name__ == "__main__":
    start_daemon()
