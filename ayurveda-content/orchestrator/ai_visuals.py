#!/usr/bin/env python3
"""
Ayurvedic Documentary Visual Generator
Produces dark, cinematic, 1080x1920 (9:16) photorealistic frames:
1. ComfyUI REST API (defaults to http://0.0.0.0:8188/ unless overridden via COMFYUI_URL)
2. Local Diffusers (SDXL-Turbo / Flux on NVIDIA GPU)
3. High-Contrast Procedural Motion Canvas (Zero-dependency offline fallback)
"""

import json
import logging
import os
from pathlib import Path
import random
import time
from typing import Dict, Any, List, Optional, Tuple
import uuid
import requests

from common.env_loader import load_project_env

load_project_env()

logger = logging.getLogger("ayurveda.ai_visuals")

# Default ComfyUI URL as requested: http://0.0.0.0:8188/ unless changed from env
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://0.0.0.0:8188/").strip().rstrip("/")


def get_comfyui_base_urls(configured_url: Optional[str] = None) -> List[str]:
    """
    Returns candidate URLs for ComfyUI.
    On Windows client sockets, connecting to 0.0.0.0 throws WinError 10049.
    We include 127.0.0.1 as an automatic client fallback for 0.0.0.0.
    """
    raw = (configured_url or os.getenv("COMFYUI_URL") or "http://0.0.0.0:8188/").strip().rstrip("/")
    urls = [raw]
    if "0.0.0.0" in raw:
        urls.append(raw.replace("0.0.0.0", "127.0.0.1"))
    elif "127.0.0.1" in raw:
        urls.append(raw.replace("127.0.0.1", "0.0.0.0"))
    return urls


def safe_comfyui_request(
    method: str,
    path: str,
    base_url: Optional[str] = None,
    **kwargs,
) -> Tuple[requests.Response, str]:
    """Executes an HTTP request across candidate ComfyUI URLs, returning (response, reachable_url)."""
    urls = get_comfyui_base_urls(base_url)
    last_err: Optional[Exception] = None
    clean_path = path.lstrip("/")

    for u in urls:
        full_url = f"{u}/{clean_path}"
        try:
            resp = requests.request(method, full_url, **kwargs)
            return resp, u
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, OSError) as e:
            last_err = e
            continue

    raise last_err or requests.exceptions.ConnectionError(f"Unable to connect to ComfyUI at {urls}")


def is_comfyui_available(base_url: Optional[str] = None) -> bool:
    """Returns True if the ComfyUI REST API is responsive and ready for inference."""
    try:
        resp, reachable_url = safe_comfyui_request("GET", "/system_stats", base_url=base_url, timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def get_available_checkpoint(base_url: Optional[str] = None) -> Optional[str]:
    """Discovers available checkpoint models installed in the ComfyUI server."""
    try:
        resp, _ = safe_comfyui_request("GET", "/object_info/CheckpointLoaderSimple", base_url=base_url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            ckpt_list = (
                data.get("CheckpointLoaderSimple", {})
                .get("input", {})
                .get("required", {})
                .get("ckpt_name", [[]])[0]
            )
            if ckpt_list and isinstance(ckpt_list, list) and len(ckpt_list) > 0:
                # Prefer SDXL, Turbo, or photorealistic checkpoints if present
                for ckpt in ckpt_list:
                    if any(k in ckpt.lower() for k in ["sdxl", "xl", "turbo", "lightning", "flux", "real", "phot"]):
                        return ckpt
                return ckpt_list[0]
    except Exception as e:
        logger.debug(f"Failed to fetch checkpoint info from ComfyUI: {e}")
    return None


def construct_cinematic_ayurveda_prompt(subject: str, scene_type: str = "macro") -> str:
    """Creates a hyper-realistic, documentary-grade visual prompt."""
    if scene_type == "cold_extinguish":
        return (
            f"Cinematic 8k photorealistic documentary shot of a tall glass of ice water splashing and freezing "
            "a glowing warm internal fire, dramatic rising steam, embers turning dark, high contrast, "
            "weathered obsidian background, shallow depth of field, National Geographic documentary style, zero text."
        )
    elif scene_type == "anatomy_fire":
        return (
            f"Sleek minimalist medical anatomical illustration of the human digestive system explaining {subject}. "
            "Dark translucent human torso silhouette, glowing warm golden energy pathways of internal digestive fire, "
            "high contrast, dark obsidian background, Apple health aesthetic, clean 8k render, no text."
        )
    elif scene_type == "toxic_waste":
        return (
            f"Cinematic dark medical visualization of {subject}. "
            "Congealed fat molecules and metabolic sludge within a stylized digestive tract, moody amber backlighting, "
            "obsidian shadows, hyper-detailed texture, National Geographic documentary style, 8k photorealistic, zero text."
        )
    elif scene_type == "remedy":
        return (
            f"Close-up of ancient authentic Ayurvedic preparation of {subject}. "
            "Handcrafted antique bronze and copper vessels, raw organic botanical ingredients, "
            "dark moody monastery lighting, warm candlelight ambient glow, cinematic composition, photorealistic 8k, zero text."
        )
    elif scene_type == "vitality":
        return (
            f"Cinematic portrait of vibrant healthy energized human with radiant skin and digestive balance. "
            "Warm golden Rembrandt rim lighting, soft dark slate stone background, peaceful confident expression, "
            "85mm portrait lens, National Geographic documentary style, zero text."
        )
    else:
        return (
            f"Cinematic 8k photorealistic documentary macro photography of {subject}. "
            "Weathered dark slate stone surface, dramatic warm golden Rembrandt rim lighting, "
            "delicate rising steam, shallow depth of field, 85mm portrait lens, National Geographic documentary style, "
            "deep obsidian shadows, zero text, hyper-detailed texture."
        )


def generate_comfyui_image(
    prompt_text: str,
    output_path: Path,
    negative_prompt: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_sec: int = 180,
) -> Optional[Path]:
    """Generates an image via ComfyUI REST API if running on the server."""
    if not is_comfyui_available(base_url):
        return None

    try:
        ckpt_name = get_available_checkpoint(base_url) or "sd_xl_base_1.0.safetensors"
        ckpt_lower = ckpt_name.lower()

        # Determine optimal resolution and sampling parameters based on model architecture
        is_sdxl = any(k in ckpt_lower for k in ["sdxl", "xl", "turbo", "lightning", "flux"])
        if is_sdxl:
            width, height = (832, 1472)  # Standard high-quality 9:16 portrait
            if "turbo" in ckpt_lower:
                steps, cfg = 4, 1.5
            elif "lightning" in ckpt_lower:
                steps, cfg = 6, 2.0
            else:
                steps, cfg = 25, 7.0
        else:
            width, height = (576, 1024)  # SD 1.5 vertical resolution
            steps, cfg = 20, 7.0

        seed = random.randint(1, 1_000_000_000)
        client_id = str(uuid.uuid4())

        neg_text = (
            negative_prompt
            or "text, watermark, logo, font, subtitle, cartoon, illustration, drawing, painting, bad anatomy, deformed, blurry"
        )

        prompt_graph = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": ckpt_name},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": 1},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt_text, "clip": ["4", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": neg_text, "clip": ["4", 1]},
            },
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "ayurveda_shot", "images": ["8", 0]},
            },
        }

        logger.info(f"Submitting prompt to ComfyUI ({ckpt_name}, {width}x{height}): {prompt_text[:60]}...")
        resp, reachable_url = safe_comfyui_request(
            "POST",
            "/prompt",
            base_url=base_url,
            json={"prompt": prompt_graph, "client_id": client_id},
            timeout=10,
        )

        if resp.status_code != 200:
            logger.warning(f"ComfyUI prompt submission failed: {resp.status_code} - {resp.text}")
            return None

        prompt_id = resp.json().get("prompt_id")
        if not prompt_id:
            logger.warning("No prompt_id returned by ComfyUI.")
            return None

        # Poll history until completion
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            try:
                h_resp, _ = safe_comfyui_request("GET", f"/history/{prompt_id}", base_url=reachable_url, timeout=5)
                if h_resp.status_code == 200:
                    h_data = h_resp.json()
                    if prompt_id in h_data:
                        history_entry = h_data[prompt_id]
                        outputs = history_entry.get("outputs", {})
                        for node_id, node_out in outputs.items():
                            images = node_out.get("images", [])
                            if images:
                                img_info = images[0]
                                filename = img_info.get("filename")
                                subfolder = img_info.get("subfolder", "")
                                img_type = img_info.get("type", "output")

                                v_resp, _ = safe_comfyui_request(
                                    "GET",
                                    f"/view?filename={filename}&subfolder={subfolder}&type={img_type}",
                                    base_url=reachable_url,
                                    timeout=30,
                                )
                                if v_resp.status_code == 200 and len(v_resp.content) > 1000:
                                    output_path.parent.mkdir(parents=True, exist_ok=True)
                                    with open(output_path, "wb") as f:
                                        f.write(v_resp.content)
                                    logger.info(f"[+] Successfully generated ComfyUI image saved to {output_path}")
                                    return output_path
            except Exception as poll_err:
                logger.debug(f"Polling ComfyUI: {poll_err}")

            time.sleep(1.5)

        logger.warning(f"ComfyUI generation timed out after {timeout_sec}s for prompt_id: {prompt_id}")
        return None
    except Exception as e:
        logger.warning(f"ComfyUI generation error: {e}")
        return None


def generate_scene_visuals(
    topic_data: Dict[str, Any],
    output_dir: Path,
    queries: Optional[List[str]] = None,
) -> List[str]:
    """
    Generates cinematic AI visual frames for the video scenes via ComfyUI.
    Returns list of saved image file paths.
    """
    if not is_comfyui_available():
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    visual_paths: List[str] = []

    subject = topic_data.get("subject", "Digestive Fire and Gut Health")
    key_fact = topic_data.get("key_fact", "Warm spiced ginger decoction stimulating enzymes")

    scene_configs = [
        {"type": "cold_extinguish", "subject": "Ice water freezing digestive stomach fire"},
        {"type": "anatomy_fire", "subject": subject},
        {"type": "toxic_waste", "subject": "Congealed undigested food and toxic metabolic sludge in intestines"},
        {"type": "remedy", "subject": key_fact},
        {"type": "vitality", "subject": "Healthy gut vitality and digestion"},
    ]

    for idx, cfg in enumerate(scene_configs, 1):
        target_file = output_dir / f"scene_{idx}.jpg"
        if target_file.exists() and target_file.stat().st_size > 1000:
            visual_paths.append(str(target_file))
            continue

        prompt = construct_cinematic_ayurveda_prompt(cfg["subject"], cfg["type"])
        result = generate_comfyui_image(prompt, target_file)
        if result and target_file.exists() and target_file.stat().st_size > 1000:
            visual_paths.append(str(target_file))

    return visual_paths
