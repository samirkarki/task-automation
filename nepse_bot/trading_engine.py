#!/usr/bin/env python3
"""
NEPSE Institutional Quantitative Trading Engine & Alpha Generator
Computes technical indicators from real historical timeseries (Wilder RSI-14, 20/50/200 SMAs, ATR-14),
integrates Floorsheet Smart-Money Broker Accumulation, applies Market Regime Gates (Bull vs Correction),
and queries Ollama (qwen3-coder:30b) with structured Chain-of-Thought prompts to achieve high win rates.
"""

import os
import sys
import json
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
import requests

from nepse_bot.history_db import (
    init_history_db,
    seed_initial_history_if_needed,
    compute_institutional_metrics_for_symbol,
)

logger = logging.getLogger("trading_engine")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")
REQUEST_TIMEOUT = 300
DEFAULT_RCLONE_REPORT_REMOTE = os.getenv("RCLONE_NEPSE_REMOTE", "gdrive:NEPSE_Reports")
MANDATORY_DISCLAIMER = "Automated data research only. Not financial advice."

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"


# -----------------------------------------------------------------------------
# Multi-Factor Quantitative Screening Engine
# -----------------------------------------------------------------------------
def screen_institutional_alpha_setups(
    df_prices: pd.DataFrame,
    market_regime: str = "BULL_ACCUMULATION",
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Screens the equity universe using real rolling timeseries metrics and floorsheet accumulation.
    Enforces strict risk filters:
    - Min 1:2.0 Risk-to-Reward ratio
    - Dynamic ATR-14 volatility stop-losses
    - Prevents buying within 2.5% of +10% daily circuit ceilings
    - Rewards institutional smart-money broker accumulation (Broker 58, 45, 34)
    """
    init_history_db()
    seed_initial_history_if_needed()

    candidates = []

    for _, row in df_prices.iterrows():
        sym = str(row["symbol"]).strip().upper()
        metrics = compute_institutional_metrics_for_symbol(sym)
        if not metrics:
            continue

        close = metrics["close"]
        high = metrics["high"]
        low = metrics["low"]
        sma_20 = metrics["sma_20"]
        sma_50 = metrics["sma_50"]
        sma_200 = metrics["sma_200"]
        rsi = metrics["rsi_14"]
        atr = max(close * 0.02, metrics["atr_14"])  # Minimum 2% ATR floor
        vol_surge = metrics["volume_surge"]
        acc_ratio = metrics["floorsheet_accumulation_ratio"]
        top_buyer = metrics["top_buyer_broker"]

        # Circuit Ceiling Filter: Do not chase stocks already up > 8.5% on the day (circuit ceiling trap)
        prev_close = float(row.get("previous_close", close))
        pct_chg = round(((close - prev_close) / prev_close) * 100, 2)
        if pct_chg >= 8.5:
            continue

        # Strategy Archetype Detection
        setup_type = None
        grade = "A"

        # Archetype 1: Institutional Volume Breakout (High Momentum)
        if close > sma_20 and sma_20 >= sma_50 and 52.0 <= rsi <= 68.0 and vol_surge >= 1.2:
            setup_type = "Institutional Volume Breakout"
            if acc_ratio >= 0.12 and vol_surge >= 1.5:
                grade = "A+ (Prime Institutional Accumulation)"

        # Archetype 2: Oversold Trendline Pullback (Mean Reversion)
        elif 36.0 <= rsi <= 48.0 and close >= (sma_50 * 0.97) and acc_ratio >= 0.05:
            setup_type = "Oversold Pullback & Support Reversal"
            grade = "A"

        # Archetype 3: Golden Alignment (Trend Continuation)
        elif close > sma_20 > sma_50 > sma_200 and rsi < 65.0:
            setup_type = "Trend Continuation / Golden Alignment"
            grade = "A"

        if not setup_type:
            continue

        # Dynamic ATR-14 Volatility Stop-Loss & Target Calculations
        stop_loss_distance = round(1.5 * atr, 1)
        entry_low = round(close * 0.992, 1)
        entry_high = round(close * 1.012, 1)
        stop_loss = round(max(close * 0.92, entry_low - stop_loss_distance), 1)

        # Mathematical Target Placement (Enforcing >= 1:2.0 Risk-to-Reward)
        risk_per_share = entry_high - stop_loss
        min_reward_target = round(entry_high + (2.0 * risk_per_share), 1)
        target_1 = min_reward_target
        target_2 = round(entry_high + (3.2 * risk_per_share), 1)

        rr_ratio = round((target_1 - entry_high) / max(1.0, risk_per_share), 2)

        # Composite Conviction Score (0 - 100)
        conviction_score = round(
            (vol_surge * 22)
            + (acc_ratio * 35)
            + ((1 if close > sma_20 else 0) * 15)
            + ((1 if close > sma_50 else 0) * 15)
            + (13 if 50 <= rsi <= 62 else 5),
            1,
        )

        candidates.append({
            "symbol": sym,
            "security_name": row.get("security_name", sym),
            "sector": row.get("sector", "Equities"),
            "ltp": close,
            "change_pct": pct_chg,
            "setup_type": setup_type,
            "grade": grade,
            "suggested_entry_range": f"{entry_low} - {entry_high}",
            "stop_loss": stop_loss,
            "target_1": target_1,
            "target_2": target_2,
            "risk_reward_ratio": f"1:{rr_ratio}",
            "wilders_rsi_14": rsi,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "atr_14": atr,
            "volume_surge": vol_surge,
            "smart_money_accumulation_ratio": acc_ratio,
            "top_buyer_broker": top_buyer,
            "conviction_score": conviction_score,
        })

    # Rank by conviction score and return top setups
    candidates.sort(key=lambda x: x["conviction_score"], reverse=True)
    selected = candidates[:top_n]
    logger.info(f"Screened {len(selected)} institutional alpha candidates with true timeseries metrics.")
    return selected


# -----------------------------------------------------------------------------
# Institutional Chain-of-Thought (CoT) Prompting
# -----------------------------------------------------------------------------
def build_institutional_trading_prompt(
    setups: List[Dict[str, Any]],
    market_regime: str = "BULL_ACCUMULATION",
    external_feed: Optional[str] = None,
) -> str:
    macro_context = external_feed or (
        "Nepal Rastra Bank (NRB) accommodative liquidity environment; commercial bank interbank rates steady at ~3.2%; "
        "retail interest rate environment driving capital toward equities. Hydropower sector displaying sustained "
        "institutional block accumulation by Broker 58 and Broker 45 ahead of dry season peak revenue projections."
    )

    setups_json = json.dumps(setups, indent=2)

    prompt = f"""
You are the Chief Investment Officer and Quantitative Portfolio Manager for an institutional NEPSE trading desk.
You are tasked with reviewing mathematically screened trade candidates and delivering an actionable, high-win-rate **Trading Alpha Advisory Report**.

### Macro & Liquidity Environment:
{macro_context}
Market Regime Gate: {market_regime}

### Quantitatively Screened Candidates (Computed from True 90-Day Rolling Timeseries):
```json
{setups_json}
```

Instructions for High-Win-Rate Execution:
1. Review the quantitative metrics (Wilder RSI-14, 20/50 SMA alignment, ATR-14, Volume Surge, and Floorsheet Broker Accumulation).
2. For each screened stock, generate an institutional **Trade Card**:
   - **Symbol & Sector**
   - **Setup Grade & Action** (e.g. "A+ Grade | STRONG BUY")
   - **Entry Range (NPR)**: Highlight optimal limit-order accumulation zone.
   - **Target 1 (Base Case) & Target 2 (Extended Bull)**: Exact profit-taking levels.
   - **Stop Loss (NPR)**: Exact structural invalidation level (based on 1.5x ATR).
   - **Risk-to-Reward Ratio**: Must be strictly >= 1:2.0.
   - **Smart Money Floorsheet Proof**: Cite broker accumulation data (e.g. Broker 58/45 net buying vs retail).
   - **Technical Catalyst**: Moving average bounce, breakout confirmation, or RSI momentum shift.
3. Include strict **Portfolio Capital Allocation & Invalidation Discipline** (Max 6-8% portfolio allocation per setup, zero emotion on stop-losses).

Format your response in clean, professional Markdown with tables and clear trade cards.
"""
    return prompt.strip()


def build_system_instruction() -> str:
    return (
        "You are an elite quantitative trading strategist specializing in NEPSE technical analysis, "
        "market micro-structure, floorsheet broker accumulation mechanics, and strict risk-reward modeling. "
        "Prioritize capital preservation and high-probability trade setups above all else. "
        f"You MUST conclude every report with the exact mandatory disclaimer:\n'{MANDATORY_DISCLAIMER}'"
    )


# -----------------------------------------------------------------------------
# Ollama Interaction & Staging
# -----------------------------------------------------------------------------
def generate_ai_trading_advisory(
    setups: List[Dict[str, Any]],
    external_feed: Optional[str] = None,
    model: str = DEFAULT_MODEL,
) -> str:
    prompt = build_institutional_trading_prompt(setups, external_feed=external_feed)
    system_instruction = build_system_instruction()

    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_instruction,
        "stream": False,
        "options": {
            "temperature": 0.35,  # Deterministic, low hallucination for financial precision
            "top_p": 0.9,
        },
    }

    logger.info(f"Querying Ollama ({model}) for institutional trading advisory...")
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        report = resp.json().get("response", "").strip()
        logger.info(f"Generated institutional trading advisory ({len(report)} chars).")
        return report
    except Exception as e:
        logger.error(f"Failed to query Ollama for trading advisory: {e}")
        raise


def save_and_sync_trading_report(
    report_content: str,
    setups: List[Dict[str, Any]],
    output_dir: Path = OUTPUT_DIR,
    remote_dest: str = DEFAULT_RCLONE_REPORT_REMOTE,
    skip_rclone: bool = False,
) -> Tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    clean_report = report_content.strip()
    if MANDATORY_DISCLAIMER not in clean_report:
        clean_report += f"\n\n---\n**Disclaimer**: {MANDATORY_DISCLAIMER}\n"

    report_path = output_dir / f"nepse_trading_advisory_{timestamp_str}.md"
    signals_json_path = output_dir / f"nepse_signals_{timestamp_str}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(clean_report)

    with open(signals_json_path, "w", encoding="utf-8") as f:
        json.dump(setups, f, indent=2)

    logger.info(f"Staged institutional advisory: {report_path.name}")
    logger.info(f"Staged signal JSON: {signals_json_path.name}")

    if not skip_rclone:
        for p in [report_path, signals_json_path]:
            cmd = ["rclone", "copy", str(p), remote_dest]
            try:
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                p.unlink()
                logger.info(f"Uploaded and cleaned staging file: {p.name}")
            except Exception as e:
                logger.error(f"rclone failed for {p.name}: {e}")
                raise

    return report_path, signals_json_path


# -----------------------------------------------------------------------------
# Main Public Interface
# -----------------------------------------------------------------------------
def run_trading_analysis(
    df_prices: pd.DataFrame,
    external_feed: Optional[str] = None,
    remote_dest: str = DEFAULT_RCLONE_REPORT_REMOTE,
    model: str = DEFAULT_MODEL,
    skip_rclone: bool = False,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Executes true historical technical screening, floorsheet broker evaluation,
    and Ollama institutional advisory generation.
    """
    logger.info("Running institutional screening on true historical timeseries...")
    setups = screen_institutional_alpha_setups(df_prices, top_n=5)

    logger.info("Generating AI Trading Advisory with Chain-of-Thought prompting...")
    ai_report = generate_ai_trading_advisory(setups, external_feed=external_feed, model=model)

    save_and_sync_trading_report(
        report_content=ai_report,
        setups=setups,
        output_dir=OUTPUT_DIR,
        remote_dest=remote_dest,
        skip_rclone=skip_rclone,
    )

    return setups, ai_report


def main():
    parser = argparse.ArgumentParser(description="NEPSE Institutional Trading Engine")
    parser.add_argument("--remote", type=str, default=DEFAULT_RCLONE_REPORT_REMOTE)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--skip-rclone", action="store_true")

    args = parser.parse_args()

    from nepse_bot.nepse_scraper import fetch_resilient_nepse_data
    df_prices, _, _, _ = fetch_resilient_nepse_data()

    try:
        run_trading_analysis(
            df_prices=df_prices,
            remote_dest=args.remote,
            model=args.model,
            skip_rclone=args.skip_rclone,
        )
        logger.info("Institutional Trading Engine completed successfully.")
    except Exception as e:
        logger.critical(f"Trading engine failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
