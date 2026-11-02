#!/usr/bin/env bash
# =============================================================================
# Automated ComfyUI AnimateDiff & VideoHelperSuite Setup Script
# Enables ComfyUI to render 9:16 AnimateDiff AI video clips (.mp4)
#
# Usage:
#   chmod +x setup_comfyui_animatediff.sh
#   ./setup_comfyui_animatediff.sh [optional_path_to_comfyui]
# =============================================================================

set -e

COMFY_DIR="${1:-}"

# Search default locations if not provided
if [ -z "$COMFY_DIR" ]; then
    for candidate in "$HOME/ComfyUI" "/home/ubuntu/ComfyUI" "/workspace/ComfyUI" "../ComfyUI" "../../ComfyUI"; do
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
    echo "  ./setup_comfyui_animatediff.sh /path/to/ComfyUI"
    echo "================================================================="
    exit 1
fi

echo "================================================================="
echo "[*] Setting up AnimateDiff video engine in ComfyUI: $COMFY_DIR"
echo "================================================================="

CUSTOM_NODES="$COMFY_DIR/custom_nodes"
MODELS_DIR="$COMFY_DIR/models/animatediff_models"
mkdir -p "$MODELS_DIR"

# 1. ComfyUI-VideoHelperSuite (VHS - saves latents directly to MP4)
if [ ! -d "$CUSTOM_NODES/ComfyUI-VideoHelperSuite" ]; then
    echo "[+] Cloning ComfyUI-VideoHelperSuite into custom_nodes..."
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git "$CUSTOM_NODES/ComfyUI-VideoHelperSuite"
    if [ -f "$CUSTOM_NODES/ComfyUI-VideoHelperSuite/requirements.txt" ]; then
        pip install -r "$CUSTOM_NODES/ComfyUI-VideoHelperSuite/requirements.txt" || true
    fi
else
    echo "[i] ComfyUI-VideoHelperSuite is already installed."
fi

# 2. ComfyUI-AnimateDiff-Evolved (motion module loader and injector)
if [ ! -d "$CUSTOM_NODES/ComfyUI-AnimateDiff-Evolved" ]; then
    echo "[+] Cloning ComfyUI-AnimateDiff-Evolved into custom_nodes..."
    git clone https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git "$CUSTOM_NODES/ComfyUI-AnimateDiff-Evolved"
    if [ -f "$CUSTOM_NODES/ComfyUI-AnimateDiff-Evolved/requirements.txt" ]; then
        pip install -r "$CUSTOM_NODES/ComfyUI-AnimateDiff-Evolved/requirements.txt" || true
    fi
else
    echo "[i] ComfyUI-AnimateDiff-Evolved is already installed."
fi

# 3. Download SD1.5 AnimateDiff Motion Model
MOTION_MODEL="$MODELS_DIR/v3_sd15_mm.ckpt"
if [ ! -f "$MOTION_MODEL" ] && [ ! -f "$MODELS_DIR/mm_sd_v15_v2.ckpt" ]; then
    echo "[+] Downloading AnimateDiff motion model checkpoint (v3_sd15_mm.ckpt, ~1.6GB)..."
    wget -c "https://huggingface.co/guoyww/animatediff/resolve/main/v3_sd15_mm.ckpt" -O "$MOTION_MODEL"
    echo "[+] Motion model downloaded successfully to $MOTION_MODEL."
else
    echo "[i] AnimateDiff motion model checkpoint already found in $MODELS_DIR."
fi

echo "================================================================="
echo "[+] AnimateDiff installation completed successfully!"
echo "[!] IMPORTANT: Restart your ComfyUI server now for changes to take effect:"
echo "    pkill -f 'python.*main.py' || true"
echo "    cd '$COMFY_DIR' && python main.py --listen 0.0.0.0 --port 8188"
echo "================================================================="
