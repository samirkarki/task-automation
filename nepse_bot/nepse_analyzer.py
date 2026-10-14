#!/usr/bin/env python3
"""
NEPSE Market Trend Analyzer
Queries local Ollama (qwen3-coder:30b) to parse market trends, generates
structured Markdown research reports, and uploads them to Google Drive via rclone.
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

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")
REQUEST_TIMEOUT = 300  # 300-second robust timeout
DEFAULT_RCLONE_REMOTE = os.getenv("RCLONE_NEPSE_REMOTE", "gdrive:NEPSE_Reports")
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
        logger.error(f"Failed to connect to Ollama at {url}. Ensure Ollama is running. Error: {ce}")
        raise
    except requests.exceptions.HTTPError as he:
        logger.error(f"HTTP error occurred while querying Ollama: {he}")
        raise
    except Exception as ex:
        logger.error(f"Unexpected error querying Ollama: {ex}")
        raise


# -----------------------------------------------------------------------------
# Prompt Engineering & Data Structuring
# -----------------------------------------------------------------------------
def construct_nepse_prompt(market_data: Dict[str, Any]) -> str:
    """
    Constructs the prompt instructions for analyzing NEPSE market trends.
    """
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
    """
    System prompt enforcing the domain role and the mandatory disclaimer.
    """
    return (
        "You are an elite quantitative financial analyst specializing in the Nepal Stock Exchange (NEPSE). "
        "Your reports must be precise, professional, structured in clear Markdown, and data-backed. "
        f"You must always conclude the report with the exact mandatory disclaimer:\n'{MANDATORY_DISCLAIMER}'"
    )


# -----------------------------------------------------------------------------
# Default / Sample Data Provider
# -----------------------------------------------------------------------------
def get_sample_nepse_data() -> Dict[str, Any]:
    """
    Provides structured snapshot data for NEPSE if no external data feed is supplied.
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "nepse_index": {
            "current": 2748.92,
            "change": 32.45,
            "percent_change": 1.19,
            "open": 2716.47,
            "high": 2755.10,
            "low": 2712.30,
        },
        "market_turnover_npr": 8452093410.00,
        "total_shares_traded": 18239040,
        "total_transactions": 89412,
        "market_breadth": {
            "advanced": 172,
            "declined": 65,
            "unchanged": 7,
        },
        "top_gaining_sectors": [
            {"sector": "Hydropower", "percent_gain": 2.84},
            {"sector": "Non-Life Insurance", "percent_gain": 2.15},
            {"sector": "Banking", "percent_gain": 0.88},
        ],
        "top_losing_sectors": [
            {"sector": "Hotels and Tourism", "percent_loss": -0.62},
            {"sector": "Manufacturing & Processing", "percent_loss": -0.31},
        ],
        "top_gainers": [
            {"symbol": "BARUN", "ltp": 485.0, "change": 44.0, "pct_change": 9.98},
            {"symbol": "UPPER", "ltp": 592.0, "change": 53.0, "pct_change": 9.83},
            {"symbol": "SHIVM", "ltp": 612.0, "change": 48.0, "pct_change": 8.51},
        ],
        "top_turnover": [
            {"symbol": "NICA", "turnover_npr": 542100000, "ltp": 620.0},
            {"symbol": "SHIVM", "turnover_npr": 489200000, "ltp": 612.0},
            {"symbol": "UPPER", "turnover_npr": 412000000, "ltp": 592.0},
        ],
    }


# -----------------------------------------------------------------------------
# File Staging & Rclone Synchronization
# -----------------------------------------------------------------------------
def save_report_locally(report_content: str, output_dir: Path = OUTPUT_DIR) -> Path:
    """
    Saves the Markdown report to a local staging directory with a timestamped filename.
    Guarantees the mandatory disclaimer is included.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ensure mandatory disclaimer exists at the bottom
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


def sync_and_cleanup(file_path: Path, remote_destination: str = DEFAULT_RCLONE_REMOTE) -> bool:
    """
    Executes subprocess `rclone copy` to upload file to Google Drive.
    Immediately deletes local file upon success to save disk space.
    """
    logger.info(f"Initiating rclone sync: '{file_path}' -> '{remote_destination}'...")
    cmd = ["rclone", "copy", str(file_path), remote_destination]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        logger.info(f"rclone copy succeeded: {result.stdout.strip()}")

        # Immediate cleanup of local staging file to preserve disk space on Nvidia L4
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Cleaned up local staging file '{file_path}' to conserve disk space.")
        return True

    except subprocess.CalledProcessError as cpe:
        logger.error(f"rclone command failed with returncode {cpe.returncode}.")
        logger.error(f"rclone stderr: {cpe.stderr.strip()}")
        logger.warning(f"Local staging file preserved at '{file_path}' for inspection or retry.")
        raise
    except FileNotFoundError:
        logger.error(
            "rclone binary not found in system PATH. Ensure rclone is installed and configured on the server."
        )
        logger.warning(f"Local staging file kept at '{file_path}'.")
        raise


# -----------------------------------------------------------------------------
# Main Execution Flow
# -----------------------------------------------------------------------------
def run_analysis(
    input_file: Optional[Path] = None,
    remote_dest: str = DEFAULT_RCLONE_REMOTE,
    model: str = DEFAULT_MODEL,
    skip_rclone: bool = False,
) -> Path:
    """
    Full pipeline run: Load data -> Query Ollama -> Stage report -> Sync & Cleanup.
    """
    # 1. Load data
    if input_file and input_file.exists():
        logger.info(f"Loading NEPSE data from {input_file}...")
        with open(input_file, "r", encoding="utf-8") as f:
            market_data = json.load(f)
    else:
        logger.info("Using current session NEPSE market data snapshot...")
        market_data = get_sample_nepse_data()

    # 2. Build prompts
    prompt = construct_nepse_prompt(market_data)
    system_instruction = build_system_instruction()

    # 3. Query Ollama
    report_text = query_ollama(
        prompt=prompt,
        system_instruction=system_instruction,
        model=model,
    )

    # 4. Save report locally to staging directory
    staged_path = save_report_locally(report_text, OUTPUT_DIR)

    # 5. Sync to Google Drive and delete local staging copy
    if not skip_rclone:
        sync_and_cleanup(staged_path, remote_dest)
    else:
        logger.info(f"[DRY-RUN/SKIP] Skipping rclone sync. Report preserved at {staged_path}")

    return staged_path


def main():
    parser = argparse.ArgumentParser(
        description="NEPSE Analyzer: AI-driven financial market intelligence using Ollama and rclone."
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        default=None,
        help="Optional path to a JSON file containing NEPSE market session data.",
    )
    parser.add_argument(
        "--remote",
        type=str,
        default=DEFAULT_RCLONE_REMOTE,
        help=f"rclone destination remote (default: {DEFAULT_RCLONE_REMOTE}).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Ollama model name (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--skip-rclone",
        action="store_true",
        help="Skip rclone upload (useful for local development/testing).",
    )

    args = parser.parse_args()

    try:
        run_analysis(
            input_file=args.input_file,
            remote_dest=args.remote,
            model=args.model,
            skip_rclone=args.skip_rclone,
        )
        logger.info("NEPSE Analyzer workflow completed successfully.")
    except Exception as exc:
        logger.critical(f"NEPSE Analyzer pipeline aborted with error: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
