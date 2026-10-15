#!/usr/bin/env bash
# =============================================================================
# Automated Infrastructure Pipeline for YetiCloud Nvidia L4 Server
# Scheduled to run Monday - Friday at 11:00 PM (and on-demand)
#
# Execution Order:
# 1. Immediate Git Pull from origin/main (First action when script starts)
# 2. Setup logging & load configuration (.env)
# 3. Initialize & activate Python virtual environment (venv/)
# 4. Sequentially execute NEPSE Intelligence and Faceless Video Pipelines
# =============================================================================

set -eo pipefail

# -----------------------------------------------------------------------------
# 1. IMMEDIATE GIT PULL (Always executed first upon startup)
# -----------------------------------------------------------------------------
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR:${PYTHONPATH:-}"

echo "================================================================="
echo "[$(date +'%Y-%m-%d %H:%M:%S')] [START] Starting run.sh in $PROJECT_DIR"
echo "[$(date +'%Y-%m-%d %H:%M:%S')] [GIT PULL] Executing 'git pull origin main' first..."
echo "================================================================="

if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    if git remote | grep -q "^origin$"; then
        if git pull origin main; then
            echo "[$(date +'%Y-%m-%d %H:%M:%S')] [GIT PULL] Successfully updated codebase from origin/main."
        else
            echo "[$(date +'%Y-%m-%d %H:%M:%S')] [WARN] 'git pull origin main' encountered an issue. Continuing with current local workspace."
        fi
    else
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] [WARN] No 'origin' remote configured yet. Skipping git pull."
    fi
else
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [WARN] Not inside a git repository. Skipping git pull."
fi

# -----------------------------------------------------------------------------
# 2. Logging Setup
# -----------------------------------------------------------------------------
LOGS_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOGS_DIR"

TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
LOG_FILE="$LOGS_DIR/pipeline_${TIMESTAMP}.log"

# Color codes for terminal logging
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
NC="\033[0m"

log_info() {
    local msg="[$(date +'%Y-%m-%d %H:%M:%S')] [INFO] $1"
    echo -e "${GREEN}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_warn() {
    local msg="[$(date +'%Y-%m-%d %H:%M:%S')] [WARN] $1"
    echo -e "${YELLOW}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_step() {
    local msg="[$(date +'%Y-%m-%d %H:%M:%S')] [STEP] $1"
    echo -e "${CYAN}=================================================================${NC}"
    echo -e "${CYAN}${msg}${NC}"
    echo -e "${CYAN}=================================================================${NC}"
    echo "=================================================================" >> "$LOG_FILE"
    echo "$msg" >> "$LOG_FILE"
    echo "=================================================================" >> "$LOG_FILE"
}

log_error() {
    local msg="[$(date +'%Y-%m-%d %H:%M:%S')] [ERROR] $1"
    echo -e "${RED}${msg}${NC}"
    echo "$msg" >> "$LOG_FILE"
}

log_info "Session log initialized at $LOG_FILE"

# -----------------------------------------------------------------------------
# 3. Load Environment Configuration
# -----------------------------------------------------------------------------
if [ -f "$PROJECT_DIR/.env" ]; then
    log_info "Loading configuration from .env..."
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +a
else
    log_warn "No .env found. Using default environment variables (copy from .env.example)."
fi

# -----------------------------------------------------------------------------
# 4. Virtual Environment Setup & Dependencies
# -----------------------------------------------------------------------------
log_step "Initializing Python virtual environment..."
VENV_DIR="${VENV_DIR:-$PROJECT_DIR/venv}"

if [ ! -d "$VENV_DIR" ]; then
    log_info "Creating new virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR" 2>&1 | tee -a "$LOG_FILE"
else
    log_info "Using virtual environment at $VENV_DIR..."
fi

if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/Scripts/activate"
else
    log_error "Could not find virtual environment activation script in $VENV_DIR!"
    exit 1
fi

log_info "Active Python: $(which python3 || which python)"

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    log_info "Synchronizing dependencies from requirements.txt..."
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r "$PROJECT_DIR/requirements.txt" 2>&1 | tee -a "$LOG_FILE"
fi

# Verify multimedia rendering dependencies
if ! command -v ffmpeg &> /dev/null; then
    log_warn "ffmpeg is not found on system PATH! Video rendering requires ffmpeg."
    log_warn "To install on YetiCloud (Ubuntu/Debian): sudo apt update && sudo apt install -y ffmpeg fonts-dejavu-core"
else
    log_info "ffmpeg binary detected: $(command -v ffmpeg)"
fi

# -----------------------------------------------------------------------------
# Check for Daemon Mode
# -----------------------------------------------------------------------------
if [ "${1:-}" = "--daemon" ]; then
    log_step "Starting Autonomous 24/7 Scheduler Daemon..."
    exec python "$PROJECT_DIR/scheduler.py"
fi

# -----------------------------------------------------------------------------
# 5. Execute NEPSE Intelligence, Scraper & Monetized Telegram Broadcaster
# -----------------------------------------------------------------------------
log_step "Running NEPSE Intelligence & Monetization Pipeline (nepse_bot/nepse_analyzer.py)..."
if python "$PROJECT_DIR/nepse_bot/nepse_analyzer.py" 2>&1 | tee -a "$LOG_FILE"; then
    log_info "NEPSE Intelligence & Monetization Pipeline completed successfully."
else
    log_error "NEPSE Intelligence Pipeline encountered an error."
    exit 1
fi

# -----------------------------------------------------------------------------
# 6. Execute Faceless Content Generator & YouTube Shorts Auto-Publisher
# -----------------------------------------------------------------------------
log_step "Running Faceless Content Generator & Social Publisher (faceless_content/content_generator.py)..."
if python "$PROJECT_DIR/faceless_content/content_generator.py" 2>&1 | tee -a "$LOG_FILE"; then
    log_info "Faceless Content Generator & Social Publisher completed successfully."
else
    log_error "Faceless Content Generator encountered an error."
    exit 1
fi

log_step "Nightly Pipeline Execution Finished Successfully!"
log_info "All tasks completed at $(date +'%Y-%m-%d %H:%M:%S'). Log saved: $LOG_FILE"
