# NEPSE Automated Revenue & Content Infrastructure

Autonomous, 24/7 revenue-generating infrastructure deployed on **YetiCloud Nvidia L4 Server**.
Transforms data collection, technical quantitative finance, and local LLM/TTS video rendering into an automated **social media and paid VIP trading signal business**.

---

## 🏛️ End-to-End Monetization Architecture

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
│ - Win-Rate Performance Audit         ├──────────────┐             │   │
└──────────────────┬───────────────────┘              │             │   │
                   │                                  │             │   │
                   ▼                                  ▼             │   │
┌──────────────────────────────────────┐  ┌───────────────────────┐ │   │
│ 3. Automated Telegram Broadcaster    │  │ 4. YouTube Shorts     │ │   │
│ - Free Channel: Teasers & Pulse      │  │    Auto-Publisher     │ │   │
│ - VIP Channel: High-Conviction Setups│  │ - 1080x1920 MP4 Video │ │   │
│ - SQLite Subscriber Management       │  │ - Telegram CTA Link   │ │   │
│ - Monetized: eSewa / Khalti Subs     │  │ - Demat Affiliate Link│ │   │
└──────────────────────────────────────┘  └───────────────────────┘ │   │
                                                                    │   │
┌──────────────────────────────────────┐                            │   │
│ 5. Macro Market Trend Analyzer       ├────────────────────────────┤   │
│ - Executive summary & sector flows   │ Markdown Reports           │   │
│ - Regulatory Disclaimer Guarantee    │                            │   │
└──────────────────────────────────────┘                            │   │
                                                                    │   │
┌──────────────────────────────────────┐                            │   │
│ 6. Faceless Text-to-Video Pipeline   │                            │   │
│ - Viral 30s Script Drafting (Ollama) ├────────────────────────────┤   │
│ - Neural TTS (Edge-TTS) Voiceover    │                            │   │
│ - MoviePy + Pillow 9:16 MP4 Renderer │ MP4, Audio, Scripts        │   │
│   (1080x1920, Animated Charts, Subs) │                            │   │
└──────────────────┬───────────────────┘                            │   │
                   │                                                │   │
                   ▼                                                ▼   ▼   ▼
       ┌───────────────────────────────┐                   ┌───────────────────────────────┐
       │   Local SSD Staging Area      │                   │   Google Drive Remote         │
       │   - nepse_bot/output/         ├──────────────────►│   via rclone:                 │
       │   - faceless_content/output/  │    rclone copy    │   - gdrive:NEPSE_Data/        │
       │   (Purged upon sync success)  │                   │   - gdrive:NEPSE_Reports/     │
       └───────────────────────────────┘                   │   - gdrive:FacelessContent/   │
                                                           └───────────────────────────────┘
```

---

## 📁 Repository Structure

```
nepse-faceless-automation/
├── .env.example                        # Complete configuration template
├── .gitignore                          # Excludes secrets, output staging, databases, venv
├── README.md                           # Master infrastructure and deployment manual
├── requirements.txt                    # requests, pandas, numpy, moviepy, edge-tts, google-api
├── run.sh                              # Master execution script (single run or --daemon mode)
├── scheduler.py                        # 24/7 autonomous daemon scheduling daily market tasks
├── systemd/
│   └── nepse-automation.service        # Production Linux systemd service configuration
├── telegram_bot/
│   ├── __init__.py
│   ├── bot_broadcaster.py              # Broadcasts Free teaser & VIP signal cards
│   └── subscriber_manager.py           # SQLite database for VIP subscribers & eSewa/Khalti renewals
├── faceless_content/
│   ├── __init__.py
│   ├── tts_engine.py                   # Neural speech synthesis with Edge-TTS & subtitles
│   ├── video_renderer.py               # MoviePy 1080x1920 MP4 vertical video renderer
│   ├── youtube_publisher.py            # YouTube Shorts auto-uploader with SEO & affiliate links
│   ├── content_generator.py            # End-to-end script-to-video auto-publisher & rclone sync
│   └── output/                         # Temporary staging (auto-cleaned upon sync)
├── nepse_bot/
│   ├── __init__.py
│   ├── nepse_scraper.py                # Session data scraper & lossless tar.gz archiver
│   ├── trading_engine.py               # Technical indicator screening + Ollama AI trade setups
│   ├── win_rate_tracker.py             # Persistent SQLite audit for win-rates & marketing proof
│   ├── nepse_analyzer.py               # Orchestrator for scraper, trading engine & Telegram
│   └── output/                         # Temporary staging (auto-cleaned upon sync)
└── logs/                               # Execution and daemon logs
```

---

## 💰 How This Infrastructure Generates Revenue

1. **VIP Paid Telegram Subscription Club (High Margin Recurring Income)**:
   * Free channel receives daily morning briefs and teaser alerts with links to join VIP.
   * VIP channel receives detailed trade cards (Entry, Target 1/2, Stop Loss, Risk/Reward).
   * 100 members @ 1,000 NPR/month = **100,000 NPR/month** pure recurring profit via eSewa/Khalti.
2. **Social Traffic & Affiliate Revenue**:
   * YouTube Shorts videos auto-publish with pinned comments directing viewers to your free Telegram channel and broker TMS registration links.
3. **Trade Win-Rate Proof**:
   * `win_rate_tracker.py` audits closed trades against subsequent market sessions to calculate and publish verified win-rate scorecards (e.g. 82.5% accuracy), driving subscriber trust and conversions.

---

## ⚙️ Prerequisites Checklist on YetiCloud Nvidia L4 Server

### 1. Ollama (`qwen3-coder:30b`)
```bash
systemctl status ollama
ollama pull qwen3-coder:30b
```

### 2. rclone Google Drive Remotes
```bash
rclone config
# Confirm access:
rclone lsd gdrive:
```

### 3. Environment Secrets Configuration (`.env`)
Copy the template and plug in your keys:
```bash
cp .env.example .env
nano .env
```
Key variables to set:
* `TELEGRAM_BOT_TOKEN`: Token from [@BotFather](https://t.me/BotFather).
* `TELEGRAM_FREE_CHANNEL_ID`: Your public Telegram channel (e.g., `@NepseAlphaFree`).
* `TELEGRAM_VIP_CHANNEL_ID`: Your private VIP subscriber channel.
* `TELEGRAM_FREE_INVITE_LINK`: Public invite link to join your channel.
* `YOUTUBE_CLIENT_SECRETS_FILE`: Path to Google Cloud OAuth Desktop `client_secrets.json` (optional for live YouTube auto-upload).

---

## 🚀 Execution & 24/7 Autonomous Operation

### Option A: Run 24/7 as a Background Systemd Service (Recommended)
This runs completely autonomously without needing terminal sessions:
```bash
# 1. Copy service file to systemd directory
sudo cp systemd/nepse-automation.service /etc/systemd/system/

# 2. Reload and start service
sudo systemctl daemon-reload
sudo systemctl enable --now nepse-automation

# 3. Check status & live logs
sudo systemctl status nepse-automation
tail -f logs/daemon.log
```

### Option B: Run 24/7 via `./run.sh --daemon`
```bash
chmod +x run.sh
./run.sh --daemon
```

### Option C: Trigger a Single Immediate Pipeline Run
```bash
./run.sh
```

### Option D: Nightly Crontab Schedule (Monday to Friday at 11:00 PM)
To run the automated pipeline every weekday night at 11:00 PM (doing `git pull` first):
```bash
crontab -e
```
Add:
```cron
0 23 * * 1-5 /bin/bash /path/to/nepse-faceless-automation/run.sh >> /path/to/nepse-faceless-automation/logs/cron.log 2>&1
```

---

## ⏰ Daily Autonomous Operating Schedule

When running in daemon mode, the server executes automatically on trading days (Sunday to Thursday):

| Time (NPT) | Automated Task | Distribution / Output |
| :--- | :--- | :--- |
| **10:45 AM** | Pre-Market Brief & Watchlist | Morning YouTube Short + Telegram update |
| **12:30 PM** | Mid-Day Momentum Pulse | Free Telegram Channel Alert |
| **03:30 PM** | Market Close Scrape + Lossless Archive | `gdrive:NEPSE_Data/` lossless tar.gz |
| **03:35 PM** | Technical Screening + AI Trade Setups | VIP Telegram Channel Trade Cards |
| **03:40 PM** | Macro Intelligence Report | `gdrive:NEPSE_Reports/` Markdown |
| **03:45 PM** | 1080x1920 MP4 Video Auto-Render | YouTube Shorts Auto-Upload + `gdrive:FacelessContent/` |
| **05:00 PM** | Win-Rate Performance Audit | Verified Win-Rate Scorecard to Telegram |

---

## 🔒 Compliance & Risk Management
All reports, trade cards, and videos automatically include the mandatory disclaimer:
> **"Automated data research only. Not financial advice."**
Trade setups strictly calculate position invalidation levels to promote capital preservation.
