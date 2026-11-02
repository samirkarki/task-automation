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
    ComfyUI defaults to 127.0.0.1:8188 or 0.0.0.0:8188 when started with --listen.
    We test canonical loopback (127.0.0.1), localhost, and 0.0.0.0.
    """
    raw = (configured_url or os.getenv("COMFYUI_URL") or "http://0.0.0.0:8188/").strip().rstrip("/")
    candidates: List[str] = []

    # If user provided a specific non-loopback IP/host, prioritize it
    if raw not in ["http://0.0.0.0:8188", "http://127.0.0.1:8188", "http://localhost:8188"]:
        candidates.append(raw)

    # Standard loopback addresses (127.0.0.1 is standard on both Linux and Windows)
    for u in ["http://127.0.0.1:8188", "http://localhost:8188", "http://0.0.0.0:8188"]:
        if u not in candidates:
            candidates.append(u)

    if raw not in candidates:
        candidates.append(raw)

    return candidates


def check_comfyui_connection(base_url: Optional[str] = None, timeout: float = 4.0) -> Tuple[bool, str, Optional[str]]:
    """
    Tests ComfyUI availability across candidate endpoints.
    Returns (is_available, diagnostic_message, reachable_url).
    """
    urls = get_comfyui_base_urls(base_url)
    diag_errors: List[str] = []

    for u in urls:
        # Check /system_stats and /prompt (GET to /prompt returns 405 Method Not Allowed if ComfyUI is up)
        for path in ["/system_stats", "/prompt"]:
            full_url = f"{u}{path}"
            try:
                resp = requests.get(full_url, timeout=timeout)
                if resp.status_code in (200, 405):
                    return True, f"Connected to ComfyUI at {u} (HTTP {resp.status_code})", u
                diag_errors.append(f"{full_url} -> HTTP {resp.status_code}")
            except (requests.exceptions.ConnectionError, OSError):
                diag_errors.append(f"{u} (connection refused)")
                break  # don't test further paths on the same host if connection refused
            except requests.exceptions.Timeout:
                diag_errors.append(f"{u} (timed out after {timeout}s)")
                break
            except Exception as e:
                diag_errors.append(f"{full_url} ({type(e).__name__}: {e})")
                break

    summary = "; ".join(diag_errors) if diag_errors else "no response"
    return False, f"ComfyUI offline or unreachable ({summary})", None


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
    available, msg, reachable_url = check_comfyui_connection(base_url=base_url)
    if available:
        logger.info(f"[+] {msg}")
    else:
        logger.warning(f"[-] {msg}")
    return available


def get_available_checkpoint(base_url: Optional[str] = None) -> Optional[str]:
    """Discovers available checkpoint models installed in the ComfyUI server."""
    try:
        resp, _ = safe_comfyui_request("GET", "/object_info/CheckpointLoaderSimple", base_url=base_url, timeout=4)
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
    """Creates a hyper-realistic, documentary-grade visual prompt adapted to the subject query."""
    subj_lower = subject.lower()

    # Anatomy, bacteria, gut fire, internal organs
    if any(k in subj_lower for k in ["anatomy", "bacteria", "gut", "stomach", "digest", "intestine", "internal"]):
        return (
            f"Sleek minimalist medical anatomical illustration explaining {subject}. "
            "Dark translucent human torso silhouette, glowing warm golden energy pathways of internal digestive metabolic fire, "
            "high contrast, dark obsidian background, Apple health documentary aesthetic, clean 8k render, zero text."
        )
    # Cold liquids, ice water, extinguishing fire
    elif any(k in subj_lower for k in ["ice", "cold", "water", "extinguish", "freeze"]):
        return (
            f"Cinematic 8k photorealistic documentary shot of {subject}. "
            "A glass of ice water splashing and extinguishing glowing warm embers, dramatic rising steam, "
            "high contrast, weathered dark obsidian background, National Geographic documentary style, zero text."
        )
    # Stale leftovers, toxic waste, fermentation, bloating
    elif any(k in subj_lower for k in ["stale", "leftover", "toxic", "waste", "bloat", "ferment", "sludge"]):
        return (
            f"Cinematic dark medical visualization of {subject}. "
            "Congealed food particles and metabolic stagnation within stylized digestive system, moody amber backlighting, "
            "obsidian shadows, hyper-detailed texture, National Geographic documentary style, 8k photorealistic, zero text."
        )
    # Vitality, smiling, healthy person
    elif any(k in subj_lower for k in ["person", "healthy", "glow", "smile", "vitality", "face"]):
        return (
            f"Cinematic portrait of vibrant healthy energized human representing {subject}. "
            "Radiant skin and inner digestive vitality, warm golden Rembrandt rim lighting, soft dark slate stone background, "
            "peaceful confident expression, 85mm portrait lens, National Geographic documentary style, zero text."
        )
    # Cooking, boiling, herbs, tea, remedies, spices, meals
    elif any(k in subj_lower for k in ["cook", "pot", "tea", "meal", "herb", "spice", "ginger", "decoction", "remedy", "serve"]):
        return (
            f"Close-up of ancient authentic Ayurvedic preparation of {subject}. "
            "Handcrafted antique bronze and copper vessels, fresh raw organic botanical ingredients, "
            "dark moody monastery lighting, warm candlelight ambient glow, cinematic composition, photorealistic 8k, zero text."
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
    max_frames: int = 6,
) -> List[str]:
    """
    Generates cinematic AI visual frames for the video scenes via ComfyUI.
    Uses the script's visual queries to generate matching scene imagery.
    Returns list of saved image file paths.
    """
    if not is_comfyui_available():
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    visual_paths: List[str] = []

    # Use queries if available to match the narrative beats exactly
    if queries and len(queries) > 0:
        subjects_to_generate = queries[:max_frames]
    else:
        subject = topic_data.get("subject", "Digestive Fire and Gut Health")
        key_fact = topic_data.get("key_fact", "Warm spiced botanical decoction stimulating digestion")
        subjects_to_generate = [
            f"Ice water freezing internal digestive heat ({subject})",
            f"Translucent anatomical gut digestion ({subject})",
            f"Congealed metabolic stagnation in intestines ({key_fact})",
            f"Warm herbal preparation ({key_fact})",
            f"Healthy energized vitality and digestion balance",
        ]

    logger.info(f"Generating {len(subjects_to_generate)} ComfyUI scene frames for topic: '{topic_data.get('subject', '')}'...")

    for idx, subj in enumerate(subjects_to_generate, 1):
        target_file = output_dir / f"scene_{idx}.jpg"
        if target_file.exists() and target_file.stat().st_size > 1000:
            logger.info(f"Reusing cached ComfyUI visual: {target_file.name}")
            visual_paths.append(str(target_file))
            continue

        prompt = construct_cinematic_ayurveda_prompt(subj)
        logger.info(f"Rendering ComfyUI frame {idx}/{len(subjects_to_generate)}: '{subj[:50]}'...")
        result = generate_comfyui_image(prompt, target_file)
        if result and target_file.exists() and target_file.stat().st_size > 1000:
            visual_paths.append(str(target_file))

    return visual_paths
