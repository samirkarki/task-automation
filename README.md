# NEPSE Faceless Automation Infrastructure

Production-ready automated financial data collection, lossless compression archive, quantitative stock analysis, AI-assisted trading suggestion engine, and viral Text-to-Speech (TTS) 9:16 vertical video auto-rendering pipeline deployed on **YetiCloud Nvidia L4 Server**.

---

## 🏛️ Comprehensive Architecture

```
                                ┌─────────────────────────────────────────┐
                                │  Local Ollama Instance                  │
                                │  Model: qwen3-coder:30b                 │
                                │  (Timeout: 300s, Port: 11434)           │
                                └───▲─────────────────▲─────────────────▲─┘
                                    │                 │                 │
                Prompt & Context ───┤                 │                 │
                                    │                 │                 │
┌───────────────────────────────────┴──┐              │                 │
│ 1. NEPSE Scraper & Data Collector    │              │                 │
│ - Live/Session Scraper (CSVs)        │              │                 │
│ - Lossless tar.gz Compression        ├──────────────┼─────────────┐   │
│ - Submits to gdrive:NEPSE_Data/      │              │             │   │
└──────────────────┬───────────────────┘              │             │   │
                   │ Tabular Data                     │             │   │
┌──────────────────▼───────────────────┐              │             │   │
│ 2. Quantitative Trading Engine       │              │             │   │
│ - Indicators: RSI, SMA/EMA, BB, Vol  ├──────────────┘             │   │
│ - Screening: Breakouts, Mean Revert  │ Structured Setups          │   │
│ - AI Trading Advisory & Risk Mgmt    ├────────────────────────┐   │   │
└──────────────────────────────────────┘                        │   │   │
                                                                │   │   │
┌──────────────────────────────────────┐                        │   │   │
│ 3. Macro Market Trend Analyzer       ├────────────────────────┤   │   │
│ - Executive summary & sector flows   │ Markdown Reports       │   │   │
│ - Regulatory Disclaimer Guarantee    │                        │   │   │
└──────────────────────────────────────┘                        │   │   │
                                                                │   │   │
┌──────────────────────────────────────┐                        │   │   │
│ 4. Faceless Text-to-Video Pipeline   │                        │   │   │
│ - Viral 30s Script Drafting (Ollama) ├────────────────────────┤   │   │
│ - Neural TTS (Edge-TTS) Voiceover    │                        │   │   │
│ - MoviePy + Pillow 9:16 MP4 Renderer │ MP4, Audio, Scripts    │   │   │
│   (1080x1920, Animated Charts, Subs) │                        │   │   │
└──────────────────┬───────────────────┘                        │   │   │
                   │                                            │   │   │
                   ▼                                            ▼   ▼   ▼
       ┌───────────────────────────────┐               ┌───────────────────────────────┐
       │   Local SSD Staging Area      │               │   Google Drive Remote         │
       │   - nepse_bot/output/         ├──────────────►│   via rclone:                 │
       │   - faceless_content/output/  │  rclone copy  │   - gdrive:NEPSE_Data/        │
       │   (Purged upon sync success)  │               │   - gdrive:NEPSE_Reports/     │
       └───────────────────────────────┘               │   - gdrive:FacelessContent/   │
                                                       └───────────────────────────────┘
```

---

## 📁 Repository Structure

```
nepse-faceless-automation/
├── .gitignore                          # Staging outputs, venv, logs, secrets, and temp assets
├── README.md                           # Complete architecture & deployment documentation
├── requirements.txt                    # requests, pandas, numpy, matplotlib, moviepy, Pillow, edge-tts
├── run.sh                              # Unified execution pipeline (executable mode 100755)
├── nepse_bot/
│   ├── __init__.py
│   ├── nepse_scraper.py                # Scrapes session data to CSV & builds lossless tar.gz archive
│   ├── trading_engine.py               # Technical screening (RSI/SMA/BB/Vol) + Ollama AI trade setups
│   ├── nepse_analyzer.py               # Orchestrator for scraper, trading engine & macro reports
│   └── output/                         # Temporary staging (auto-cleaned upon sync)
├── faceless_content/
│   ├── __init__.py
│   ├── tts_engine.py                   # Edge-TTS neural speech synthesis & subtitle timing
│   ├── video_renderer.py               # MoviePy 1080x1920 MP4 vertical video renderer with dynamic subs
│   ├── content_generator.py            # End-to-end script-to-video auto-publisher & rclone sync
│   └── output/                         # Temporary staging (auto-cleaned upon sync)
└── logs/                               # Timestamped execution logs
```

---

## ⚙️ Prerequisites on YetiCloud Nvidia L4 Server

### 1. Ollama & Qwen3-Coder
Ensure Ollama is running on the Nvidia L4 GPU with `qwen3-coder:30b`:
```bash
systemctl status ollama
ollama pull qwen3-coder:30b
ollama list
```

### 2. rclone Google Drive Remotes
Ensure `rclone` is authenticated with Google Drive:
```bash
rclone config
# Confirm access
rclone lsd gdrive:
```
The automated pipeline targets:
- `gdrive:NEPSE_Data/`: Lossless compressed `.tar.gz` datasets (stock prices, sectoral indices, market summary).
- `gdrive:NEPSE_Reports/`: Daily macro trend analysis reports and AI-assisted trading advisory reports.
- `gdrive:FacelessContent/`: Rendered 1080x1920 `.mp4` video files, `.mp3` voiceovers, scripts, and JSON manifests.

---

## 🚀 Execution & Usage

### 1. Run Complete Automated Infrastructure
The master bash script navigates to the project directory, pulls the latest Git updates, activates the shared virtual environment, and runs both the NEPSE intelligence pipeline and the text-to-video renderer sequentially:
```bash
chmod +x run.sh
./run.sh
```

### 2. Standalone NEPSE Intelligence & Scraper
```bash
# Full scraping + lossless compression + trading analysis + macro report
python nepse_bot/nepse_analyzer.py

# Standalone Scraper & Lossless Archiver
python nepse_bot/nepse_scraper.py --remote gdrive:NEPSE_Data/

# Standalone AI Trading Suggestion Engine
python nepse_bot/trading_engine.py --remote gdrive:NEPSE_Reports/
```

### 3. Standalone Faceless Text-to-Video Generator
```bash
# Full Script -> TTS Audio -> 1080x1920 MP4 Video -> Google Drive Sync
python faceless_content/content_generator.py

# Optional Flags:
# --topic "Why Hydropower stocks are surging in NEPSE"
# --skip-video    # Draft script & manifest only (skip MP4 render)
# --skip-rclone   # Keep rendered video and audio in output/ for inspection
```

---

## ⏰ Cron Automation
Schedule the entire automated pipeline to run every trading day after market close (Sunday to Thursday at 3:30 PM Nepal time):
```bash
crontab -e
```
Add:
```cron
30 15 * * 0-4 /bin/bash /path/to/nepse-faceless-automation/run.sh >> /path/to/nepse-faceless-automation/logs/cron.log 2>&1
```

---

## 🔒 Compliance & Risk Management
All reports and trading intelligence cards generated by the platform include the mandatory disclaimer:
> **"Automated data research only. Not financial advice."**
All trading setups include explicit Stop-Loss invalidation levels and Risk-to-Reward parameters.
