#!/usr/bin/env python3
"""
Telegram Bot Signal Broadcaster
Automatically broadcasts daily market recaps and high-conviction quantitative trade setups
to Telegram channels:
- Free Community Channel: Market sentiment, top gainers, and teaser alert with VIP invite.
- VIP Paid Channel: Full actionable trade cards (Entry, Targets, Stop Loss, Risk/Reward, Rationale).
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional

import requests

logger = logging.getLogger("telegram_broadcaster")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_FREE_CHANNEL_ID = os.getenv("TELEGRAM_FREE_CHANNEL_ID", "")
TELEGRAM_VIP_CHANNEL_ID = os.getenv("TELEGRAM_VIP_CHANNEL_ID", "")
TELEGRAM_FREE_INVITE_LINK = os.getenv("TELEGRAM_FREE_INVITE_LINK", "https://t.me/your_nepse_channel")
MANDATORY_DISCLAIMER = "Automated data research only. Not financial advice."


# -----------------------------------------------------------------------------
# Telegram API Wrapper
# -----------------------------------------------------------------------------
def send_telegram_message(
    chat_id: str,
    text: str,
    bot_token: Optional[str] = None,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> bool:
    """
    Sends an HTML-formatted message to a specified Telegram channel or group.
    """
    token = bot_token or TELEGRAM_BOT_TOKEN
    if not token or token == "your_telegram_bot_token_here":
        logger.warning(
            "[TELEGRAM] TELEGRAM_BOT_TOKEN is not set or placeholder. Skipping broadcast. "
            "Configure it in .env to enable live automated broadcasts."
        )
        return False

    if not chat_id:
        logger.warning("[TELEGRAM] Target chat_id is empty. Skipping message send.")
        return False

    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }

    try:
        response = requests.post(api_url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("ok"):
            logger.info(f"[TELEGRAM] Message successfully sent to {chat_id}.")
            return True
        else:
            logger.error(f"[TELEGRAM] API response error: {data}")
            return False
    except Exception as exc:
        logger.error(f"[TELEGRAM] Failed to send message to {chat_id}: {exc}")
        return False


# -----------------------------------------------------------------------------
# Formatting Engines
# -----------------------------------------------------------------------------
def format_free_channel_teaser(
    nepse_index: float,
    index_change: float,
    turnover_npr: float,
    top_gainers: List[Dict[str, Any]],
    breakout_count: int = 3,
    vip_invite_link: str = TELEGRAM_FREE_INVITE_LINK,
) -> str:
    """
    Constructs high-engagement HTML broadcast for the Free Telegram Channel.
    Designed to provide immediate market value while driving conversions to VIP.
    """
    date_str = datetime.now().strftime("%B %d, %Y")
    sign = "+" if index_change >= 0 else ""
    direction_emoji = "🟢" if index_change >= 0 else "🔴"
    turnover_cr = round(turnover_npr / 10000000, 2)  # Convert to Crores

    msg = f"📊 <b>NEPSE DAILY MARKET PULSE | {date_str}</b>\n\n"
    msg += f"• <b>Index</b>: <code>{nepse_index:.2f}</code> ({direction_emoji} {sign}{index_change:.2f})\n"
    msg += f"• <b>Total Turnover</b>: <code>NPR {turnover_cr:.2f} Crore</code>\n\n"

    msg += "🔥 <b>TOP SESSION MOVERS:</b>\n"
    for g in top_gainers[:3]:
        sym = g.get("symbol", "N/A")
        ltp = g.get("close_price") or g.get("ltp", 0.0)
        pct = g.get("percent_change", 0.0)
        msg += f"  • <b>{sym}</b>: NPR {ltp} (+{pct}%)\n"

    msg += "\n⚡ <b>ALGORITHM ALERT:</b>\n"
    msg += (
        f"Our quantitative AI screening engine detected <b>{breakout_count} high-probability trade setups</b> "
        f"breaking out with heavy institutional volume accumulation.\n\n"
        f"👉 <i>Full trade cards (Entry Ranges, Target 1 & 2, Invalidation Stop-Loss) are published in our VIP Channel.</i>\n\n"
        f"💎 <b><a href='{vip_invite_link}'>Upgrade to VIP Signal Club</a></b>\n\n"
        f"⚠️ <i>{MANDATORY_DISCLAIMER}</i>"
    )
    return msg


def format_vip_trade_cards(setups: List[Dict[str, Any]]) -> str:
    """
    Constructs high-conviction, actionable trade cards for the Paid VIP Telegram Channel.
    """
    date_str = datetime.now().strftime("%B %d, %Y")
    msg = f"🎯 <b>VIP ALPHA PICKS & QUANTITATIVE SETUPS</b>\n"
    msg += f"📅 <i>Session: {date_str}</i>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━\n\n"

    for i, s in enumerate(setups, 1):
        sym = s.get("symbol", "N/A")
        sec = s.get("sector", "Equities")
        strategy = s.get("setup_type") or s.get("strategy", "Momentum Breakout")
        grade = s.get("grade", "A Grade")
        entry = s.get("suggested_entry_range", "Current Market Price")
        target1 = s.get("target_1", 0.0)
        target2 = s.get("target_2", 0.0)
        stop = s.get("stop_loss", 0.0)
        rr = s.get("risk_reward_ratio", "1:2.0")
        rsi = s.get("wilders_rsi_14") or s.get("rsi_14", 50.0)
        top_buyer = s.get("top_buyer_broker", "Institutional Broker")
        vol_surge = s.get("volume_surge", 1.0)

        msg += f"<b>{i}. {sym}</b> ({sec}) | <b>{grade}</b>\n"
        msg += f"• <b>Strategy</b>: {strategy}\n"
        msg += f"• <b>Entry Zone</b>: <code>NPR {entry}</code>\n"
        msg += f"• <b>Target 1</b>: <code>NPR {target1}</code>\n"
        msg += f"• <b>Target 2 (Extended)</b>: <code>NPR {target2}</code>\n"
        msg += f"• <b>Stop Loss (ATR Invalidation)</b>: <code>NPR {stop}</code>\n"
        msg += f"• <b>Risk/Reward</b>: {rr} | <b>Wilder RSI(14)</b>: {rsi}\n"
        msg += f"• <b>Floorsheet Signal</b>: {top_buyer} accumulation (Vol: {vol_surge}x avg)\n\n"

    msg += (
        f"🛡️ <b>Risk Management Rule:</b> Never allocate more than 5-8% of total portfolio capital "
        f"to any single setup. Strictly honor stop-loss invalidation levels.\n\n"
        f"⚠️ <i>{MANDATORY_DISCLAIMER}</i>"
    )
    return msg


# -----------------------------------------------------------------------------
# Main Broadcast Dispatcher
# -----------------------------------------------------------------------------
def broadcast_all(
    setups: List[Dict[str, Any]],
    nepse_index: float = 2748.92,
    index_change: float = 32.45,
    turnover_npr: float = 8452093410.0,
    top_gainers: Optional[List[Dict[str, Any]]] = None,
    free_channel: Optional[str] = None,
    vip_channel: Optional[str] = None,
) -> Dict[str, bool]:
    """
    Broadcasts both Free teaser and VIP signal cards to respective Telegram channels.
    """
    free_ch = free_channel or TELEGRAM_FREE_CHANNEL_ID
    vip_ch = vip_channel or TELEGRAM_VIP_CHANNEL_ID

    results = {"free": False, "vip": False}

    gainers = top_gainers or setups[:3]

    # 1. Free Channel Broadcast
    if free_ch:
        free_text = format_free_channel_teaser(
            nepse_index=nepse_index,
            index_change=index_change,
            turnover_npr=turnover_npr,
            top_gainers=gainers,
            breakout_count=len(setups),
        )
        results["free"] = send_telegram_message(free_ch, free_text)
    else:
        logger.info("[TELEGRAM] TELEGRAM_FREE_CHANNEL_ID not configured. Skipping free broadcast.")

    # 2. VIP Channel Broadcast
    if vip_ch:
        vip_text = format_vip_trade_cards(setups)
        results["vip"] = send_telegram_message(vip_ch, vip_text)
    else:
        logger.info("[TELEGRAM] TELEGRAM_VIP_CHANNEL_ID not configured. Skipping VIP broadcast.")

    return results


def main():
    parser = argparse.ArgumentParser(description="Telegram Bot Signal Broadcaster")
    parser.add_argument("--test", action="store_true", help="Send test message to check bot connectivity.")
    parser.add_argument("--message", type=str, default="Test ping from YetiCloud Nvidia L4 server.", help="Custom message text.")
    parser.add_argument("--chat-id", type=str, default=None, help="Target Telegram chat or channel ID.")

    args = parser.parse_args()

    target = args.chat_id or TELEGRAM_FREE_CHANNEL_ID or TELEGRAM_VIP_CHANNEL_ID
    if args.test:
        if not target:
            logger.error("No target channel ID provided. Pass --chat-id or set TELEGRAM_FREE_CHANNEL_ID in .env.")
            sys.exit(1)
        success = send_telegram_message(target, f"🤖 <b>SYSTEM CHECK:</b> {args.message}")
        if success:
            logger.info("Telegram connectivity verified successfully!")
        else:
            logger.warning("Telegram test message failed. Check BOT_TOKEN and channel permissions.")


if __name__ == "__main__":
    main()
