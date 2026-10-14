# NEPSE Faceless Automation Infrastructure

Production-ready automated financial research analysis and viral short-form content generation pipeline deployed on **YetiCloud Nvidia L4 Server**.

---

## 🏛️ Architecture Overview

```
                               ┌────────────────────────────────┐
                               │  Local Ollama Instance         │
                               │  Model: qwen3-coder:30b        │
                               │  (Timeout: 300s, Port: 11434)  │
                               └───────────────▲────────────────┘
                                               │ HTTP POST
                                               │
┌──────────────────────┐      ┌────────────────┴───────────────┐      ┌───────────────────────────┐
│                      │      │                                │      │                           │
│  nepse_analyzer.py   ├─────►│  Local SSD Staging Area        ├─────►│  Google Drive Remote      │
│  - Trend Analysis    │      │  - nepse_bot/output/           │      │  via rclone:              │
│  - Markdown Report   │      │  - faceless_content/output/    │      │  - gdrive:NEPSE_Reports   │
│  - Disclaimer Lock   │      │                                │      │  - gdrive:FacelessContent │
│                      │      │  (Deleted immediately after    │      │                           │
├──────────────────────┤      │   successful upload)           │      └───────────────────────────┘
│                      │      │                                │
│ content_generator.py ├─────►│                                │
│  - 30s Viral Scripts │      │                                │
│  - Manifest Metadata │      │                                │
└──────────────────────┘      └────────────────────────────────┘
```

---

## 📁 Repository Structure

```
nepse-faceless-automation/
├── .gitignore                      # Ignore venv, logs, secrets, output staging
├── README.md                       # Infrastructure & run guide
├── requirements.txt                # requests, pandas, schedule, moviepy
├── run.sh                          # Unified execution entrypoint (chmod +x)
├── nepse_bot/
│   ├── __init__.py
│   ├── nepse_analyzer.py           # NEPSE market trend analysis & rclone sync
│   └── output/                     # Temporary staging (auto-cleaned)
├── faceless_content/
│   ├── __init__.py
│   ├── content_generator.py        # 30-second viral script generator & sync
│   └── output/                     # Temporary staging (auto-cleaned)
└── logs/                           # Automated pipeline execution logs
```

---

## ⚙️ Prerequisites on YetiCloud Nvidia L4 Server

### 1. Ollama & Model Pull
Ensure Ollama is running and the `qwen3-coder:30b` model is loaded onto the Nvidia L4 GPU:
```bash
# Check if ollama service is active
systemctl status ollama

# Pull model (requires ~18GB VRAM on Nvidia L4)
ollama pull qwen3-coder:30b

# Verify
ollama list
```

### 2. rclone Configuration
Ensure `rclone` has authenticated access to Google Drive:
```bash
rclone config
# Configure remote named 'gdrive'
rclone lsd gdrive:
```
Required remotes:
- `gdrive:NEPSE_Reports`
- `gdrive:FacelessContent/`

---

## 🚀 Execution

### Run Full Pipeline via `run.sh`
The root `run.sh` script handles everything:
1. Navigates to project directory.
2. Pulls latest updates (`git pull origin main`).
3. Activates or sets up the shared virtual environment (`venv/`).
4. Installs/updates dependencies (`requirements.txt`).
5. Runs `nepse_analyzer.py` (queries Ollama, saves report, rclones to `gdrive:NEPSE_Reports`, deletes local copy).
6. Runs `content_generator.py` (queries Ollama, drafts script + manifest, rclones to `gdrive:FacelessContent/`, deletes local copy).
7. Writes timestamped execution logs to `logs/`.

```bash
chmod +x run.sh
./run.sh
```

---

## 🛠️ Standalone Component Usage

### 1. NEPSE Market Trend Analyzer
```bash
python nepse_bot/nepse_analyzer.py --help

# Optional flags:
# --input-file <path_to_json>   Pass custom session data (defaults to current snapshot)
# --remote <rclone_dest>        Override default remote (gdrive:NEPSE_Reports)
# --model <model_name>          Override model (default: qwen3-coder:30b)
# --skip-rclone                 Preserve files locally without uploading (for testing)
```

### 2. Faceless Content Generator
```bash
python faceless_content/content_generator.py --help

# Optional flags:
# --topic "<topic>"             Custom video topic
# --context "<context>"         Market context highlights
# --remote <rclone_dest>        Override default remote (gdrive:FacelessContent/)
# --model <model_name>          Override model (default: qwen3-coder:30b)
# --skip-rclone                 Preserve files locally without uploading (for testing)
```

---

## ⏰ Cron Scheduling on Server
To run automatically every trading day at 3:30 PM (after NEPSE market close):
```bash
crontab -e
```
Add:
```cron
30 15 * * 0-4 /bin/bash /path/to/nepse-faceless-automation/run.sh >> /path/to/nepse-faceless-automation/logs/cron.log 2>&1
```

---

## 🔒 Mandatory Compliance Note
Every analysis report generated by `nepse_analyzer.py` automatically includes the mandatory regulatory disclaimer:
> **"Automated data research only. Not financial advice."**
