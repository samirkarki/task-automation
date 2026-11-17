#!/usr/bin/env bash
# =============================================================================
# Automated ComfyUI LTX-Video (DiT) & VideoHelperSuite Setup Script
# Configures ComfyUI on NVIDIA GPU (24GB VRAM) for Theatrical 24fps Image-to-Video
#
# Usage:
#   chmod +x setup_comfyui_ltxvideo.sh
#   ./setup_comfyui_ltxvideo.sh [optional_path_to_comfyui]
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
    echo "  ./setup_comfyui_ltxvideo.sh /path/to/ComfyUI"
    echo "================================================================="
    exit 1
fi

echo "================================================================="
echo "[*] Setting up LTX-Video DiT Theatrical Video Engine in: $COMFY_DIR"
echo "================================================================="

CUSTOM_NODES="$COMFY_DIR/custom_nodes"
CHECKPOINTS_DIR="$COMFY_DIR/models/checkpoints"
CLIP_DIR="$COMFY_DIR/models/clip"
TEXT_ENCODERS_DIR="$COMFY_DIR/models/text_encoders"

mkdir -p "$CHECKPOINTS_DIR"
mkdir -p "$CLIP_DIR"
mkdir -p "$TEXT_ENCODERS_DIR"

# 1. ComfyUI-VideoHelperSuite (VHS - saves latents directly to 24fps MP4)
if [ ! -d "$CUSTOM_NODES/ComfyUI-VideoHelperSuite" ]; then
    echo "[+] Cloning ComfyUI-VideoHelperSuite into custom_nodes..."
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git "$CUSTOM_NODES/ComfyUI-VideoHelperSuite"
    if [ -f "$CUSTOM_NODES/ComfyUI-VideoHelperSuite/requirements.txt" ]; then
        pip install -r "$CUSTOM_NODES/ComfyUI-VideoHelperSuite/requirements.txt" || true
    fi
else
    echo "[i] ComfyUI-VideoHelperSuite is already installed. Pulling latest..."
    (cd "$CUSTOM_NODES/ComfyUI-VideoHelperSuite" && git pull || true)
fi

# 2. ComfyUI-LTXVideo (Official Lightricks DiT custom nodes)
if [ ! -d "$CUSTOM_NODES/ComfyUI-LTXVideo" ]; then
    echo "[+] Cloning ComfyUI-LTXVideo into custom_nodes..."
    git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git "$CUSTOM_NODES/ComfyUI-LTXVideo"
    if [ -f "$CUSTOM_NODES/ComfyUI-LTXVideo/requirements.txt" ]; then
        pip install -r "$CUSTOM_NODES/ComfyUI-LTXVideo/requirements.txt" || true
    fi
else
    echo "[i] ComfyUI-LTXVideo is already installed. Pulling latest..."
    (cd "$CUSTOM_NODES/ComfyUI-LTXVideo" && git pull || true)
fi

# 3. Download LTX-Video Checkpoint (v0.9.1, ~4.7GB)
LTX_MODEL="$CHECKPOINTS_DIR/ltx-video-2b-v0.9.1.safetensors"
if [ ! -f "$LTX_MODEL" ] && [ ! -f "$CHECKPOINTS_DIR/ltx-video-2b-v0.9.safetensors" ]; then
    echo "[+] Downloading LTX-Video 2B checkpoint (ltx-video-2b-v0.9.1.safetensors, ~4.7GB)..."
    wget -c "https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2b-v0.9.1.safetensors" -O "$LTX_MODEL"
    echo "[+] LTX-Video checkpoint downloaded successfully to $LTX_MODEL."
else
    echo "[i] LTX-Video checkpoint already found in $CHECKPOINTS_DIR."
fi

# 4. Download T5-XXL FP8 Text Encoder (~4.9GB) for dense prompt understanding
T5_MODEL="$TEXT_ENCODERS_DIR/t5xxl_fp8_e4m3fn.safetensors"
if [ ! -f "$T5_MODEL" ] && [ ! -f "$CLIP_DIR/t5xxl_fp8_e4m3fn.safetensors" ] && [ ! -f "$CLIP_DIR/t5xxl_fp16.safetensors" ]; then
    echo "[+] Downloading T5-XXL FP8 text encoder (t5xxl_fp8_e4m3fn.safetensors, ~4.9GB)..."
    wget -c "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors" -O "$T5_MODEL"
    # Create symlink in clip/ directory as well for loaders that search models/clip
    ln -sf "$T5_MODEL" "$CLIP_DIR/t5xxl_fp8_e4m3fn.safetensors" || cp -u "$T5_MODEL" "$CLIP_DIR/" || true
    echo "[+] T5-XXL text encoder downloaded successfully to $T5_MODEL."
else
    echo "[i] T5-XXL text encoder already present in models directory."
fi

# 5. Restart ComfyUI in tmux session 'comfy' if active, or restart process
echo "================================================================="
echo "[*] Restarting ComfyUI server..."
echo "================================================================="

if command -v tmux >/dev/null 2>&1 && tmux has-session -t comfy 2>/dev/null; then
    echo "[+] Found active tmux session 'comfy'. Restarting ComfyUI..."
    tmux send-keys -t comfy C-c
    sleep 2
    tmux send-keys -t comfy "cd '$COMFY_DIR' && python main.py --listen 0.0.0.0 --port 8188 --highvram" C-m
    echo "[+] Restart command sent to tmux session 'comfy'."
else
    echo "[!] tmux session 'comfy' not found. Restarting process directly..."
    pkill -f "python.*main.py" || true
    sleep 2
    nohup python "$COMFY_DIR/main.py" --listen 0.0.0.0 --port 8188 --highvram > "$COMFY_DIR/comfyui.log" 2>&1 &
    echo "[+] ComfyUI launched in background (PID: $!)."
fi

# 6. Verify ComfyUI node registry
echo "[*] Waiting 10 seconds for ComfyUI to initialize..."
sleep 10

echo "[*] Verifying ComfyUI LTX-Video node registration..."
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8188/object_info/LTXVImgToVideo || true)
if [ "$STATUS_CODE" = "200" ]; then
    echo "================================================================="
    echo "✅ SUCCESS: LTXVImgToVideo node is registered and active in ComfyUI!"
    echo "================================================================="
else
    echo "================================================================="
    echo "[i] Checking ComfyUI general health (HTTP $STATUS_CODE)..."
    GEN_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8188/system_stats || true)
    if [ "$GEN_STATUS" = "200" ]; then
        echo "✅ ComfyUI is running! Node registry is initializing."
    else
        echo "[!] ComfyUI is still starting up. Please check: tmux attach -t comfy"
    fi
    echo "================================================================="
fi
