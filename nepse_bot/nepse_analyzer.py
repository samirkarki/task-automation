#!/usr/bin/env python3
"""
NEPSE Market Intelligence & Trading Suggestion Orchestrator
Coordinates:
1. Session scraping & lossless CSV tar.gz archiving to Google Drive (gdrive:NEPSE_Data/).
2. Quantitative technical indicators calculation & stock screening.
3. AI-Assisted Trading Advisory generation via Ollama (qwen3-coder:30b).
4. Macro Market Trend report generation with mandatory compliance disclaimer.
5. Google Drive synchronization via rclone with automatic local staging cleanup.
"""

import os
import sys
import json
import logging
import argparse
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import requests

from nepse_bot.nepse_scraper import scrape_and_archive_nepse
from nepse_bot.trading_engine import run_trading_analysis

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")
REQUEST_TIMEOUT = 300  # 300-second robust timeout
DEFAULT_RCLONE_REPORT_REMOTE = os.getenv("RCLONE_NEPSE_REMOTE", "gdrive:NEPSE_Reports")
DEFAULT_RCLONE_DATA_REMOTE = os.getenv("RCLONE_DATA_REMOTE", "gdrive:NEPSE_Data/")
MANDATORY_DISCLAIMER = "Automated data research only. Not financial advice."

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"

# -----------------------------------------------------------------------------
# Logging Setup
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("nepse_analyzer")


# -----------------------------------------------------------------------------
# Ollama Interaction
# -----------------------------------------------------------------------------
def query_ollama(
    prompt: str,
    system_instruction: str,
    model: str = DEFAULT_MODEL,
    url: str = OLLAMA_URL,
    timeout: int = REQUEST_TIMEOUT,
) -> str:
    """
    Sends a generation request to the local Ollama instance with a 300s timeout.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system_instruction,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
        },
    }

    logger.info(f"Dispatching query to Ollama at {url} using model '{model}' (timeout={timeout}s)...")
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        generated_text = result.get("response", "").strip()

        if not generated_text:
            raise ValueError("Received empty response from Ollama generate API.")

        logger.info(f"Successfully generated response ({len(generated_text)} characters).")
        return generated_text

    except requests.exceptions.Timeout:
        logger.error(f"Ollama request timed out after {timeout} seconds.")
        raise
    except requests.exceptions.ConnectionError as ce:
        logger.error(f"Failed to connect to Ollama at {url}. Error: {ce}")
        raise
    except Exception as ex:
        logger.error(f"Unexpected error querying Ollama: {ex}")
        raise


# -----------------------------------------------------------------------------
# Prompt Engineering & Data Structuring
# -----------------------------------------------------------------------------
def construct_nepse_prompt(market_data: Dict[str, Any]) -> str:
    data_str = json.dumps(market_data, indent=2)

    prompt = f"""
You are provided with the latest Nepal Stock Exchange (NEPSE) market session data below:

```json
{data_str}
```

Please perform a rigorous financial and technical trend analysis on this NEPSE data.
Produce a comprehensive Markdown report adhering to the following structure:

# NEPSE Daily Market Intelligence & Trend Analysis
- **Trading Date / Session**: [Indicate Session Date / Time]
- **Market Stance**: [Bullish / Bearish / Neutral Consolidation]

## 1. Executive Summary & Index Dynamics
- NEPSE Index level, net point change, percentage change.
- Total Market Turnover (NPR) & volume flow analysis compared to typical baseline.
- Advance / Decline ratio (Market Breadth).

## 2. Sectoral Performance Breakdown
- Top leading/gaining sectors and their driving factors.
- Lagging sectors experiencing distribution or profit booking.
- Relative strength comparison across Banking, Hydropower, Insurance, and Non-Life.

## 3. Top Movers & Liquidity Heatmap
- Top 5 Gainers: Price action, potential catalysts, volume spikes.
- Top 5 Losers: Drawdown extent, selling pressure indicators.
- High Turnover Leaders: Where the institutional and smart money flowed.

## 4. Technical Trend & Key Levels
- Immediate support and resistance zones for the benchmark index.
- Momentum indicators and market sentiment diagnosis.
- Risk factors to monitor for the upcoming trading sessions.

## 5. Strategic Takeaways
- Key data-backed observations for short-term and medium-term market participants.

Ensure your analysis is data-driven, objective, and professional.
"""
    return prompt.strip()


def build_system_instruction() -> str:
    return (
        "You are an elite quantitative financial analyst specializing in the Nepal Stock Exchange (NEPSE). "
        "Your reports must be precise, professional, structured in clear Markdown, and data-backed. "
        f"You must always conclude the report with the exact mandatory disclaimer:\n'{MANDATORY_DISCLAIMER}'"
    )


# -----------------------------------------------------------------------------
# File Staging & Rclone Synchronization
# -----------------------------------------------------------------------------
def save_report_locally(report_content: str, output_dir: Path = OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    clean_report = report_content.strip()
    if MANDATORY_DISCLAIMER not in clean_report:
        clean_report += f"\n\n---\n**Disclaimer**: {MANDATORY_DISCLAIMER}\n"

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"nepse_report_{timestamp_str}.md"
    file_path = output_dir / filename

    logger.info(f"Writing staged report to {file_path}...")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(clean_report)

    logger.info(f"Staged report saved successfully ({file_path.stat().st_size} bytes).")
    return file_path


def sync_and_cleanup(file_path: Path, remote_destination: str = DEFAULT_RCLONE_REPORT_REMOTE) -> bool:
    logger.info(f"Initiating rclone sync: '{file_path}' -> '{remote_destination}'...")
    cmd = ["rclone", "copy", str(file_path), remote_destination]

    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        logger.info(f"rclone copy succeeded for {file_path.name}.")

        if file_path.exists():
            file_path.unlink()
            logger.info(f"Cleaned up local staging file '{file_path}' to conserve disk space.")
        return True

    except subprocess.CalledProcessError as cpe:
        logger.error(f"rclone command failed with returncode {cpe.returncode}: {cpe.stderr.strip()}")
        logger.warning(f"Local staging file preserved at '{file_path}'.")
        raise
    except FileNotFoundError:
        logger.error("rclone binary not found in PATH.")
        logger.warning(f"Local staging file kept at '{file_path}'.")
        raise


# -----------------------------------------------------------------------------
# Main Orchestrated Workflow
# -----------------------------------------------------------------------------
def run_full_nepse_pipeline(
    data_remote: str = DEFAULT_RCLONE_DATA_REMOTE,
    report_remote: str = DEFAULT_RCLONE_REPORT_REMOTE,
    model: str = DEFAULT_MODEL,
    skip_rclone: bool = False,
    external_feed: Optional[str] = None,
):
    """
    1. Scrape NEPSE CSV data & upload lossless tar.gz archive to Google Drive.
    2. Compute technical indicators & generate AI Trading Suggestions.
    3. Generate Macro Market Intelligence Report & upload to Google Drive.
    """
    logger.info("=== STEP 1/3: Scraping NEPSE Session Data & Creating Lossless Archive ===")
    csv_files, archive_path, df_prices = scrape_and_archive_nepse(
        output_dir=OUTPUT_DIR,
        remote_dest=data_remote,
        skip_rclone=skip_rclone,
    )

    logger.info("=== STEP 2/3: Quantitative Stock Analysis & AI Trading Suggestions ===")
    setups, trading_report = run_trading_analysis(
        df_prices=df_prices,
        external_feed=external_feed,
        remote_dest=report_remote,
        model=model,
        skip_rclone=skip_rclone,
    )

    logger.info("=== STEP 3/3: Generating Macro Market Trend Report via Ollama ===")
    # Extract session summary for macro report
    market_data = {
        "timestamp": datetime.now().isoformat(),
        "total_traded_records": len(df_prices),
        "top_volume_symbols": df_prices.nlargest(5, "total_traded_quantity")[["symbol", "close_price", "percent_change", "total_traded_quantity"]].to_dict(orient="records"),
        "top_turnover_symbols": df_prices.nlargest(5, "total_traded_value")[["symbol", "close_price", "total_traded_value"]].to_dict(orient="records"),
        "top_gainers": df_prices.nlargest(5, "percent_change")[["symbol", "close_price", "percent_change"]].to_dict(orient="records"),
        "top_losers": df_prices.nsmallest(5, "percent_change")[["symbol", "close_price", "percent_change"]].to_dict(orient="records"),
    }

    macro_prompt = construct_nepse_prompt(market_data)
    system_instruction = build_system_instruction()
    macro_report_text = query_ollama(macro_prompt, system_instruction, model=model)

    staged_macro_report = save_report_locally(macro_report_text, OUTPUT_DIR)
    if not skip_rclone:
        sync_and_cleanup(staged_macro_report, remote_destination=report_remote)
    else:
        logger.info(f"[DRY-RUN/SKIP] Macro report preserved locally at {staged_macro_report}")

    logger.info("NEPSE Full Intelligence & Trading Pipeline completed successfully.")


def main():
    parser = argparse.ArgumentParser(
        description="NEPSE Full Intelligence, Scraper & AI Trading Suggestion Pipeline"
    )
    parser.add_argument("--data-remote", type=str, default=DEFAULT_RCLONE_DATA_REMOTE, help=f"rclone destination for data archives (default: {DEFAULT_RCLONE_DATA_REMOTE}).")
    parser.add_argument("--report-remote", type=str, default=DEFAULT_RCLONE_REPORT_REMOTE, help=f"rclone destination for reports (default: {DEFAULT_RCLONE_REPORT_REMOTE}).")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL}).")
    parser.add_argument("--external-feed", type=str, default=None, help="Optional macro economic or news sentiment feed.")
    parser.add_argument("--skip-rclone", action="store_true", help="Skip rclone upload (local testing).")

    args = parser.parse_args()

    try:
        run_full_nepse_pipeline(
            data_remote=args.data_remote,
            report_remote=args.report_remote,
            model=args.model,
            skip_rclone=args.skip_rclone,
            external_feed=args.external_feed,
        )
    except Exception as exc:
        logger.critical(f"NEPSE Pipeline failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
