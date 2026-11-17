#!/usr/bin/env bash
# =============================================================================
# Automated ComfyUI Wan2.1 (SOTA 14B / 1.3B DiT) Setup Script
# Configures Alibaba's Wan2.1 Image-to-Video Engine on 24GB NVIDIA GPU
#
# Usage:
#   chmod +x setup_comfyui_wan21.sh
#   ./setup_comfyui_wan21.sh [optional_path_to_comfyui]
# =============================================================================

set -e

COMFY_DIR="${1:-}"

# Search default locations if not provided
if [ -z "$COMFY_DIR" ]; then
    for candidate in "$HOME/ComfyUI" "/home/ubuntu/ComfyUI" "/workspace/ComfyUI" "/root/ComfyUI" "../ComfyUI" "../../ComfyUI"; do
        if [ -d "$candidate/custom_nodes" ]; then
            COMFY_DIR="$candidate"
            break
        fi
    done
fi

if [ -z "$COMFY_DIR" ] || [ ! -d "$COMFY_DIR/custom_nodes" ]; then
    echo "================================================================="
    echo "[!] ComfyUI directory not found in default paths."
    echo "Please run this script specifying your ComfyUI root directory:"
    echo "  ./setup_comfyui_wan21.sh /path/to/ComfyUI"
    echo "================================================================="
    exit 1
fi

echo "================================================================="
echo "[*] Setting up Wan2.1 Theatrical DiT Video Engine in: $COMFY_DIR"
echo "================================================================="

CUSTOM_NODES="$COMFY_DIR/custom_nodes"
DIFFUSION_MODELS="$COMFY_DIR/models/diffusion_models"
CHECKPOINTS_DIR="$COMFY_DIR/models/checkpoints"
TEXT_ENCODERS_DIR="$COMFY_DIR/models/text_encoders"
VAE_DIR="$COMFY_DIR/models/vae"

mkdir -p "$DIFFUSION_MODELS"
mkdir -p "$CHECKPOINTS_DIR"
mkdir -p "$TEXT_ENCODERS_DIR"
mkdir -p "$VAE_DIR"

# 1. ComfyUI-WanVideoWrapper (Official / Community SOTA wrapper)
if [ ! -d "$CUSTOM_NODES/ComfyUI-WanVideoWrapper" ]; then
    echo "[+] Cloning ComfyUI-WanVideoWrapper into custom_nodes..."
    git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git "$CUSTOM_NODES/ComfyUI-WanVideoWrapper" || true
    if [ -f "$CUSTOM_NODES/ComfyUI-WanVideoWrapper/requirements.txt" ]; then
        pip install -r "$CUSTOM_NODES/ComfyUI-WanVideoWrapper/requirements.txt" || true
    fi
else
    echo "[i] ComfyUI-WanVideoWrapper is already present. Pulling latest..."
    (cd "$CUSTOM_NODES/ComfyUI-WanVideoWrapper" && git pull || true)
fi

# 2. Check VRAM and recommend model tier
VRAM_GB=24
if command -v nvidia-smi >/dev/null 2>&1; then
    VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n 1 || echo "24000")
    VRAM_GB=$((VRAM_MB / 1024))
    echo "[i] Detected GPU with ${VRAM_GB} GB VRAM."
fi

# 3. Model Download Links (Wan2.1-I2V-14B-FP8 or Wan2.1-I2V-1.3B)
echo "================================================================="
echo "[*] Wan2.1 Model Checkpoint Availability:"
echo "    - Wan2.1-I2V-14B-FP8: Best photorealism, human anatomy & cloth physics (~14GB)"
echo "    - Wan2.1-I2V-1.3B: Fast 2.7GB model for rapid iteration"
echo "================================================================="

WAN_14B_FILE="$DIFFUSION_MODELS/wan2.1_i2v_720p_14B_fp8.safetensors"
if [ ! -f "$WAN_14B_FILE" ] && [ ! -f "$CHECKPOINTS_DIR/wan2.1_i2v_720p_14B_fp8.safetensors" ]; then
    echo "[*] Download command for Wan2.1 14B-FP8 (Optimal for 24GB L4 GPU):"
    echo "    wget -c 'https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-I2V-14B-720P_fp8_e4m3fn.safetensors' -O '$WAN_14B_FILE'"
fi

# 4. Restart ComfyUI in tmux session 'comfy' with --highvram
if command -v tmux >/dev/null 2>&1 && tmux has-session -t comfy 2>/dev/null; then
    echo "[+] Found active tmux session 'comfy'. Restarting ComfyUI..."
    tmux send-keys -t comfy C-c
    sleep 2
    tmux send-keys -t comfy "cd '$COMFY_DIR' && python main.py --listen 0.0.0.0 --port 8188 --highvram" C-m
    echo "[+] Restart command sent to tmux session 'comfy'."
fi

echo "================================================================="
echo "✅ Wan2.1 environment configured successfully in ComfyUI!"
echo "================================================================="
