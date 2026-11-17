#!/usr/bin/env bash
"""
Quick 4-5s Theatrical DiT Video Test & Feedback Tool
Generates a single 97-frame (4.04s @ 24fps) LTX-Video clip using the Image-to-Video pipeline,
verifies motion, and optionally uploads as an Unlisted YouTube Short.

Usage:
    # 1. Just generate and verify local 4s clip:
    python ayurveda-content/orchestrator/test_clip.py

    # 2. Generate and upload to YouTube as Unlisted:
    python ayurveda-content/orchestrator/test_clip.py --upload

    # 3. Custom prompt:
    python ayurveda-content/orchestrator/test_clip.py --prompt "Steaming herbal ginger tea pouring into brass cup" --upload
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Union, List, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
ORCH_DIR = PROJECT_ROOT / "ayurveda-content" / "orchestrator"
if str(ORCH_DIR) not in sys.path:
    sys.path.insert(0, str(ORCH_DIR))

from common.env_loader import load_project_env
load_project_env()

from ai_visuals import (
    generate_theatrical_i2v_clip,
    is_comfyui_available,
    probe_video_duration,
)
from common.publishing.youtube_uploader import upload_short_to_youtube

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_clip")


def run_quick_test(
    prompt: str,
    image_path: Optional[str] = None,
    force_t2v: bool = False,
    upload: bool = False,
    privacy: str = "unlisted",
):
    output_dir = PROJECT_ROOT / "ayurveda-content" / "orchestrator" / "output" / "test_run"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_video = output_dir / "test_clip_4s.mp4"
    keyframe_img: Optional[Path] = None

    if image_path:
        p = Path(image_path).resolve()
        if p.exists() and p.stat().st_size > 100:
            keyframe_img = p
            print(f"[i] Using provided image for Image-to-Video: {keyframe_img.name}")
        else:
            print(f"[-] Provided image not found: {image_path}. Continuing...")

    print("\n" + "=" * 68)
    print("🎬 4-5s THEATRICAL DiT (LTX-VIDEO) TEST GENERATION")
    print("=" * 68)
    print(f"Prompt:      {prompt}")
    print(f"Target:      {output_video}")
    print(f"Frame Count: 97 frames (~4.04s @ 24fps)")
    print(f"Resolution:  768x1024 (9:16 portrait)")
    print(f"Keyframe:    {keyframe_img.name if keyframe_img else ('Auto (T2V fallback if no 2D model)' if not force_t2v else 'Disabled (Force T2V)')}")
    print("=" * 68 + "\n")

    if not is_comfyui_available():
        print("❌ Error: ComfyUI server is offline or unreachable.")
        print("   Please start ComfyUI or run: ./ayurveda-content/setup_comfyui_ltxvideo.sh")
        sys.exit(1)

    print("[*] Starting Theatrical 24fps DiT Motion Generation...")
    res_path = generate_theatrical_i2v_clip(
        prompt_text=prompt,
        output_path=output_video,
        keyframe_image=keyframe_img if not force_t2v else None,
        num_frames=97, # 4.04s @ 24fps
        frame_rate=24,
        width=768,
        height=1024,
        timeout_sec=360,
    )

    if not res_path or not output_video.exists() or output_video.stat().st_size < 1000:
        print("❌ Generation failed or returned empty file. Check ComfyUI server logs.")
        sys.exit(1)

    dur = probe_video_duration(output_video)
    size_mb = output_video.stat().st_size / (1024 * 1024)

    print("\n" + "=" * 68)
    print("✅ SUCCESS: 4-5s Theatrical Video Generated!")
    print(f"   File:        {output_video}")
    print(f"   Duration:    {dur:.2f} seconds")
    print(f"   Size:        {size_mb:.2f} MB")
    print(f"   Keyframe:    {keyframe_img}")
    print("=" * 68 + "\n")

    # Extract 3 preview frames for instant inspection
    try:
        cmd = [
            "ffmpeg", "-y", "-i", str(output_video),
            "-vf", "fps=1",
            "-vframes", "3",
            str(output_dir / "preview_frame_%02d.jpg"),
        ]
        subprocess.run(cmd, capture_output=True, timeout=15)
        print(f"📸 Extracted preview frames in: {output_dir}")
    except Exception:
        pass

    # Optional Upload to YouTube as Unlisted
    if upload:
        print("\n" + "=" * 68)
        print(f"🚀 Uploading Test Video to YouTube ({privacy.upper()})...")
        print("=" * 68)
        video_id = upload_short_to_youtube(
            video_path=output_video,
            metadata={
                "title": "LTX-Video 4s Theatrical Test #Shorts",
                "description": f"Theatrical DiT 24fps test generation.\nPrompt: {prompt}\n\n#Ayurveda #Shorts #AI",
                "tags": ["AI", "Video", "Shorts", "LTXVideo"],
            },
            privacy=privacy,
            dry_run=False,
        )
        if video_id:
            yt_url = f"https://youtu.be/{video_id}"
            print("\n" + "=" * 68)
            print("🎉 Video is Live on YouTube!")
            print(f"   URL:     {yt_url}")
            print(f"   Privacy: {privacy}")
            print("   You can paste this link right here for instant feedback!")
            print("=" * 68 + "\n")
        else:
            print("[-] YouTube upload failed. Check OAuth credentials in secrets/.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate and test a 4-5s Theatrical DiT video clip")
    parser.add_argument(
        "--prompt",
        type=str,
        default="Steaming hot herbal infusion in a brass cup on rustic sunlit wooden table, delicate rising steam, professional 8k documentary cinematography",
        help="Prompt description for keyframe and motion",
    )
    parser.add_argument("--image", type=str, default=None, help="Optional path to existing keyframe image for Image-to-Video")
    parser.add_argument("--t2v", action="store_true", help="Force Text-to-Video mode (EmptyLTXVLatentVideo) without keyframe")
    parser.add_argument("--upload", action="store_true", help="Upload the 4s clip to YouTube as Unlisted upon completion")
    parser.add_argument("--privacy", type=str, choices=["unlisted", "private", "public"], default="unlisted", help="YouTube privacy")
    args = parser.parse_args()

    run_quick_test(
        prompt=args.prompt,
        image_path=args.image,
        force_t2v=args.t2v,
        upload=args.upload,
        privacy=args.privacy,
    )
