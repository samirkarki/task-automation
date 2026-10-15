#!/usr/bin/env python3
"""
24/7 Automated Revenue & Infrastructure Scheduler Daemon
Runs autonomously on YetiCloud Nvidia L4 server.
Orchestrates multi-slot daily operations aligned with Nepal Stock Exchange (Sun-Thu):
- 10:45 AM NPT: Pre-market briefing & morning short-form video
- 12:30 PM NPT: Mid-day momentum breakout alert
- 03:30 PM NPT: Market close scrape, lossless archive, AI trading setups, Telegram broadcast & YouTube short
- 05:00 PM NPT: Win-rate performance scorecard audit & broadcast
"""

import sys
import time
import signal
import logging
from datetime import datetime
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import schedule

from nepse_bot.nepse_analyzer import run_full_nepse_pipeline
from faceless_content.content_generator import run_generator
from nepse_bot.win_rate_tracker import generate_performance_scorecard, format_telegram_scorecard
from telegram_bot.bot_broadcaster import send_telegram_message, TELEGRAM_FREE_CHANNEL_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [DAEMON] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scheduler_daemon")

IS_RUNNING = True


def handle_shutdown(signum, frame):
    global IS_RUNNING
    logger.info("Received termination signal. Shutting down scheduler gracefully...")
    IS_RUNNING = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


# -----------------------------------------------------------------------------
# Scheduled Jobs
# -----------------------------------------------------------------------------
def is_nepse_trading_day() -> bool:
    """
    NEPSE trades Sunday (6) through Thursday (3).
    Python weekday(): Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6.
    """
    weekday = datetime.now().weekday()
    return weekday in [6, 0, 1, 2, 3]


def job_pre_market_brief():
    if not is_nepse_trading_day():
        logger.info("[SCHEDULE] Weekend - skipping pre-market brief.")
        return

    logger.info(">>> EXECUTING 10:45 AM: Pre-Market Watchlist & Morning Video <<<")
    try:
        run_generator(
            topic="Top 3 NEPSE Stocks on High Alert Ahead of Today's Market Open",
            context="Pre-market sentiment, sector rotation cues, banking and hydropower watchlevels.",
        )
    except Exception as e:
        logger.error(f"Error in pre-market brief job: {e}")


def job_midday_alert():
    if not is_nepse_trading_day():
        return

    logger.info(">>> EXECUTING 12:30 PM: Mid-Day Momentum Alert <<<")
    try:
        if TELEGRAM_FREE_CHANNEL_ID:
            send_telegram_message(
                TELEGRAM_FREE_CHANNEL_ID,
                "⚡ <b>MID-DAY NEPSE MOMENTUM PULSE:</b>\n"
                "Volume expanding in Hydropower and Commercial Banks. Smart money accumulation detected.\n"
                "Stay disciplined and strictly follow risk-to-reward boundaries."
            )
    except Exception as e:
        logger.error(f"Error in midday alert job: {e}")


def job_market_close_pipeline():
    if not is_nepse_trading_day():
        logger.info("[SCHEDULE] Weekend - skipping market close pipeline.")
        return

    logger.info(">>> EXECUTING 03:30 PM: Full Market Close & Monetization Pipeline <<<")
    try:
        # 1. Scrape, archive, AI trading setups, Telegram broadcast & reports
        run_full_nepse_pipeline()

        # 2. Render & upload evening market wrap YouTube Short
        run_generator(
            topic="NEPSE Market Close Wrap & Explosive Stocks for Tomorrow's Session",
            context="Session closing index, sector leaders, turnover surge and institutional accumulation.",
        )
    except Exception as e:
        logger.error(f"Error in market close pipeline job: {e}")


def job_scorecard_broadcast():
    if not is_nepse_trading_day():
        return

    logger.info(">>> EXECUTING 05:00 PM: Win-Rate Performance Scorecard Broadcast <<<")
    try:
        scorecard = generate_performance_scorecard()
        msg = format_telegram_scorecard(scorecard)
        if TELEGRAM_FREE_CHANNEL_ID:
            send_telegram_message(TELEGRAM_FREE_CHANNEL_ID, msg)
    except Exception as e:
        logger.error(f"Error in scorecard broadcast job: {e}")


# -----------------------------------------------------------------------------
# Main Scheduler Loop
# -----------------------------------------------------------------------------
def run_daemon():
    logger.info("=================================================================")
    logger.info("Starting Autonomous 24/7 Revenue Scheduler on YetiCloud Nvidia L4")
    logger.info("Trading Days: Sunday - Thursday")
    logger.info("  • 10:45 AM NPT - Pre-Market Video & Watchlist")
    logger.info("  • 12:30 PM NPT - Mid-Day Momentum Alert")
    logger.info("  • 03:30 PM NPT - Data Scrape, Tar.gz, AI Signals, Telegram, YouTube")
    logger.info("  • 05:00 PM NPT - Verified Win-Rate Scorecard")
    logger.info("=================================================================")

    # Register schedules
    schedule.every().day.at("10:45").do(job_pre_market_brief)
    schedule.every().day.at("12:30").do(job_midday_alert)
    schedule.every().day.at("15:30").do(job_market_close_pipeline)
    schedule.every().day.at("17:00").do(job_scorecard_broadcast)

    while IS_RUNNING:
        schedule.run_pending()
        time.sleep(10)

    logger.info("Scheduler daemon stopped.")


if __name__ == "__main__":
    run_daemon()
