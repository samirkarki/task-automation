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
import sys
import time
from typing import Dict, Any, List, Optional, Tuple
import uuid
import requests

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


def get_available_checkpoint(base_url: Optional[str] = None, prefer_sd15: bool = False) -> Optional[str]:
    """
    Discovers available checkpoint models installed in the ComfyUI server.
    If prefer_sd15 is True (e.g., for AnimateDiff), prioritizes SD 1.5 checkpoints.
    Otherwise prioritizes SDXL / photorealistic checkpoints.
    """
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
                if prefer_sd15:
                    for ckpt in ckpt_list:
                        c_lower = ckpt.lower()
                        if not any(k in c_lower for k in ["sdxl", "xl", "flux", "cascade"]):
                            return ckpt
                # Prefer SDXL, Turbo, or photorealistic checkpoints if present
                for ckpt in ckpt_list:
                    if any(k in ckpt.lower() for k in ["sdxl", "xl", "turbo", "lightning", "flux", "real", "phot"]):
                        return ckpt
                return ckpt_list[0]
    except Exception as e:
        logger.debug(f"Failed to fetch checkpoint info from ComfyUI: {e}")
    return None


def get_available_motion_model(base_url: Optional[str] = None) -> Optional[str]:
    """Discovers available AnimateDiff motion models installed in ComfyUI."""
    try:
        resp, _ = safe_comfyui_request("GET", "/object_info/ADE_LoadAnimateDiffModel", base_url=base_url, timeout=4)
        if resp.status_code == 200:
            data = resp.json().get("ADE_LoadAnimateDiffModel", {})
            models = data.get("input", {}).get("required", {}).get("model_name", [[]])[0]
            if models and isinstance(models, list) and len(models) > 0:
                for m in models:
                    if any(k in m.lower() for k in ["v3", "v2", "mm_sd_v15"]):
                        return m
                return models[0]
    except Exception as e:
        logger.debug(f"Failed to fetch motion model info from ComfyUI: {e}")
    return None


def detect_comfyui_capabilities(base_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Queries ComfyUI /object_info to detect installed custom nodes and video capabilities:
    - AnimateDiff (ADE_ApplyAnimateDiffModel / ADE_LoadAnimateDiffModel)
    - VideoHelperSuite (VHS_VideoCombine)
    - SVD (SVD_img2vid_Conditioning)
    """
    caps: Dict[str, Any] = {
        "available": False,
        "animatediff": False,
        "vhs": False,
        "svd": False,
        "can_generate_video": False,
        "motion_model": None,
        "checkpoint": None,
        "sd15_checkpoint": None,
    }

    if not is_comfyui_available(base_url):
        return caps

    caps["available"] = True

    # 1. Check VideoHelperSuite (VHS_VideoCombine)
    try:
        resp, _ = safe_comfyui_request("GET", "/object_info/VHS_VideoCombine", base_url=base_url, timeout=4)
        if resp.status_code == 200 and "VHS_VideoCombine" in resp.json():
            caps["vhs"] = True
    except Exception:
        pass

    # 2. Check AnimateDiff-Evolved nodes
    try:
        resp, _ = safe_comfyui_request("GET", "/object_info/ADE_LoadAnimateDiffModel", base_url=base_url, timeout=4)
        if resp.status_code == 200 and "ADE_LoadAnimateDiffModel" in resp.json():
            caps["animatediff"] = True
            caps["motion_model"] = get_available_motion_model(base_url)
    except Exception:
        pass

    if not caps["animatediff"]:
        for alt_node in ["ADE_ApplyAnimateDiffModel", "AnimateDiffLoaderV1"]:
            try:
                resp, _ = safe_comfyui_request("GET", f"/object_info/{alt_node}", base_url=base_url, timeout=4)
                if resp.status_code == 200 and alt_node in resp.json():
                    caps["animatediff"] = True
                    break
            except Exception:
                pass

    # 3. Check SVD
    try:
        resp, _ = safe_comfyui_request("GET", "/object_info/SVD_img2vid_Conditioning", base_url=base_url, timeout=4)
        if resp.status_code == 200 and "SVD_img2vid_Conditioning" in resp.json():
            caps["svd"] = True
    except Exception:
        pass

    caps["checkpoint"] = get_available_checkpoint(base_url)
    caps["sd15_checkpoint"] = get_available_checkpoint(base_url, prefer_sd15=True)

    if caps["vhs"] and caps["animatediff"] and caps["motion_model"]:
        caps["can_generate_video"] = True

    return caps


def generate_contextual_scene_prompts(
    script_json: Dict[str, Any],
    topic_data: Dict[str, Any],
    num_scenes: int = 6,
) -> List[str]:
    """
    Uses Ollama LLM to generate rich, cinematographic scene descriptions from the full narrative.
    Instead of literal keyword searches, creates prompts that convey the underlying metabolic,
    biological, and philosophical meaning of each narrative beat.
    """
    eng_script = script_json.get("english_script", {})
    hook = eng_script.get("hook", "")
    body = eng_script.get("body", "")
    cta = eng_script.get("cta", "")

    cards = script_json.get("cards", {})
    warning_title = cards.get("warning_title", "")
    warning_sub = cards.get("warning_subtitle", "")
    remedy_title = cards.get("remedy_title", "")
    remedy_sub = cards.get("remedy_subtitle", "")

    subject = topic_data.get("subject") or script_json.get("topic", "Ayurvedic Health")
    key_fact = topic_data.get("key_fact", "")
    dosha = topic_data.get("dosha", "Digestive & Metabolic Balance")

    system_prompt = f"""You are an elite cinematic visual director and prompt engineer for National Geographic / BBC-style medical and wellness documentaries.
Your task is to generate exactly {num_scenes} vivid, photorealistic, documentary-grade visual prompts for an AI text-to-image/video model (SDXL / Stable Diffusion).

CORE PHILOSOPHY:
Do NOT produce generic literal depictions of random isolated keywords (e.g. do not just show a literal clock for '24 hours', or a generic person smiling).
Instead, each scene prompt MUST visually communicate the underlying conceptual narrative, metabolic biological mechanisms, emotional tension, and therapeutic wisdom of that specific beat in the video.

NARRATIVE ARC REQUIREMENTS (Chronological):
- Early scenes: Visualise the routine habit, contrast, tension, or the harmful action (e.g. ice water pouring over hot embers, extinguishing digestive fire).
- Middle scenes: Visualise the internal biological mechanism, cellular/metabolic dynamics, toxic stagnation (Ama/sludge) or impaired digestive fire, rich glowing amber/obsidian medical cinematography.
- Later scenes: Visualise the authentic ancient preparation, steaming spiced botanical infusion, raw medicinal roots and copper vessels, followed by rejuvenated holistic vitality.

VISUAL STYLE GUIDELINES:
- Photorealistic 8k, National Geographic documentary cinematography.
- Dark obsidian slate backgrounds, dramatic warm golden Rembrandt rim lighting, macro focus, shallow depth of field, subtle rising steam or ambient glow.
- Strictly NO text, no logos, no typography, no watermarks, no split screens, no cartoons.
- Keep each scene prompt between 25 and 45 words, focused purely on visual sensory descriptors (lighting, textures, mood, camera framing).

Output MUST be strictly valid JSON matching:
{{
  "scene_prompts": [
    "Scene 1 description...",
    "Scene 2 description...",
    "Scene 3 description...",
    "Scene 4 description...",
    "Scene 5 description...",
    "Scene 6 description..."
  ]
}}"""

    user_prompt = f"""Generate {num_scenes} contextual documentary scene prompts for:
Subject: {subject}
Key Medical/Health Fact: {key_fact}
System/Constitution: {dosha}

Full Narrative Script:
[HOOK]: {hook}
[BODY]: {body}
[CTA]: {cta}

Core Health Warning: {warning_title} ({warning_sub})
Actionable Ancient Remedy: {remedy_title} ({remedy_sub})

Return exactly {num_scenes} rich cinematic scene prompts in JSON."""

    try:
        from common.ollama_client import query_ollama_json
        data = query_ollama_json(prompt=user_prompt, system=system_prompt, timeout=90)
        raw_prompts = data.get("scene_prompts", [])
        if isinstance(raw_prompts, list) and len(raw_prompts) > 0:
            prompts = [str(p).strip() for p in raw_prompts if str(p).strip()]
            if len(prompts) >= min(3, num_scenes):
                logger.info(f"[+] Successfully generated {len(prompts)} contextual LLM scene prompts.")
                return prompts[:num_scenes]
    except Exception as e:
        logger.warning(f"Contextual LLM scene prompt generation failed ({e}). Falling back to algorithmic prompts.")

    return []


def construct_cinematic_ayurveda_prompt(subject: str, scene_type: str = "macro") -> str:
    """Creates a hyper-realistic, documentary-grade visual prompt adapted to the subject query."""
    subj_lower = subject.lower()

    # If the subject is already a rich contextual prompt (e.g. from LLM scene generator), preserve it
    if len(subject.split()) > 15 or "photorealistic" in subj_lower or "documentary" in subj_lower:
        if "zero text" not in subj_lower and "no text" not in subj_lower:
            return f"{subject.rstrip('. ')}, National Geographic documentary style, zero text, photorealistic 8k."
        return subject

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


def generate_comfyui_video(
    prompt_text: str,
    output_path: Path,
    negative_prompt: Optional[str] = None,
    base_url: Optional[str] = None,
    num_frames: int = 24,
    frame_rate: int = 8,
    timeout_sec: int = 600,
) -> Optional[Path]:
    """
    Generates a 9:16 short video clip via ComfyUI AnimateDiff + VHS_VideoCombine.
    Falls back gracefully if AnimateDiff or motion models are unavailable.
    Returns output_path if successful, None otherwise.
    """
    if not is_comfyui_available(base_url):
        return None

    caps = detect_comfyui_capabilities(base_url)
    if not caps.get("can_generate_video"):
        logger.debug("ComfyUI server lacks AnimateDiff or VHS nodes. Video generation skipped.")
        return None

    ckpt_name = caps.get("sd15_checkpoint") or caps.get("checkpoint")
    motion_model = caps.get("motion_model") or get_available_motion_model(base_url)

    if not ckpt_name or not motion_model:
        logger.warning(f"Missing required models for video: ckpt={ckpt_name}, motion_model={motion_model}")
        return None

    seed = random.randint(1, 1_000_000_000)
    client_id = str(uuid.uuid4())
    neg_text = (
        negative_prompt
        or "text, watermark, logo, font, subtitle, cartoon, illustration, drawing, painting, bad anatomy, deformed, blurry, static, flicker"
    )

    # 512x768 is the optimal 9:16 portrait resolution for SD1.5 AnimateDiff
    width, height = 512, 768
    steps, cfg = 20, 7.0

    prompt_graph = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ckpt_name},
        },
        "2": {
            "class_type": "ADE_LoadAnimateDiffModel",
            "inputs": {"model_name": motion_model},
        },
        "3": {
            "class_type": "ADE_ApplyAnimateDiffModel",
            "inputs": {
                "model": ["1", 0],
                "motion_model": ["2", 0],
            },
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": num_frames},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt_text, "clip": ["1", 1]},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": neg_text, "clip": ["1", 1]},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["3", 0],
                "positive": ["5", 0],
                "negative": ["6", 0],
                "latent_image": ["4", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["7", 0], "vae": ["1", 2]},
        },
        "9": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["8", 0],
                "frame_rate": frame_rate,
                "loop_count": 0,
                "filename_prefix": "ayurveda_anim",
                "format": "video/h264-mp4",
                "pingpong": false,
                "save_output": true,
            },
        },
    }

    try:
        logger.info(f"Submitting AnimateDiff video prompt to ComfyUI ({ckpt_name} + {motion_model}, {num_frames} frames): {prompt_text[:60]}...")
        resp, reachable_url = safe_comfyui_request(
            "POST",
            "/prompt",
            base_url=base_url,
            json={"prompt": prompt_graph, "client_id": client_id},
            timeout=10,
        )

        if resp.status_code != 200:
            logger.warning(f"ComfyUI video prompt submission failed: {resp.status_code} - {resp.text}")
            return None

        prompt_id = resp.json().get("prompt_id")
        if not prompt_id:
            return None

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
                            video_list = node_out.get("gifs") or node_out.get("videos") or node_out.get("images") or []
                            if video_list:
                                vid_info = video_list[0]
                                filename = vid_info.get("filename")
                                subfolder = vid_info.get("subfolder", "")
                                vid_type = vid_info.get("type", "output")

                                v_resp, _ = safe_comfyui_request(
                                    "GET",
                                    f"/view?filename={filename}&subfolder={subfolder}&type={vid_type}",
                                    base_url=reachable_url,
                                    timeout=60,
                                )
                                if v_resp.status_code == 200 and len(v_resp.content) > 1000:
                                    output_path.parent.mkdir(parents=True, exist_ok=True)
                                    with open(output_path, "wb") as f:
                                        f.write(v_resp.content)
                                    logger.info(f"[+] Successfully generated ComfyUI video saved to {output_path}")
                                    return output_path
            except Exception as poll_err:
                logger.debug(f"Polling ComfyUI video: {poll_err}")

            time.sleep(2.5)

        logger.warning(f"ComfyUI video generation timed out after {timeout_sec}s for prompt_id: {prompt_id}")
        return None
    except Exception as e:
        logger.warning(f"ComfyUI video generation error: {e}")
        return None


def generate_scene_visuals(
    topic_data: Dict[str, Any],
    output_dir: Path,
    queries: Optional[List[str]] = None,
    script_json: Optional[Dict[str, Any]] = None,
    max_frames: int = 6,
) -> List[str]:
    """
    Generates cinematic AI visual frames or video clips for the video scenes via ComfyUI.
    Uses contextual LLM prompts from the full narrative script when available.
    Automatically generates video clips if AnimateDiff is available on ComfyUI,
    otherwise generates photorealistic still images.
    Returns list of saved visual file paths (.mp4 or .jpg).
    """
    if not is_comfyui_available():
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    visual_paths: List[str] = []

    # 1. Determine prompts: prefer contextual LLM prompts from full narrative
    scene_prompts: List[str] = []
    if script_json:
        scene_prompts = generate_contextual_scene_prompts(
            script_json=script_json,
            topic_data=topic_data,
            num_scenes=max_frames,
        )

    # Fallback to visual queries or topic subjects if contextual LLM prompts unavailable
    if not scene_prompts:
        if queries and len(queries) > 0:
            scene_prompts = [construct_cinematic_ayurveda_prompt(q) for q in queries[:max_frames]]
        else:
            subject = topic_data.get("subject", "Digestive Fire and Gut Health")
            key_fact = topic_data.get("key_fact", "Warm spiced botanical decoction stimulating digestion")
            fallback_subjects = [
                f"Ice water freezing internal digestive heat ({subject})",
                f"Translucent anatomical gut digestion ({subject})",
                f"Congealed metabolic stagnation in intestines ({key_fact})",
                f"Warm herbal preparation ({key_fact})",
                f"Healthy energized vitality and digestion balance",
            ]
            scene_prompts = [construct_cinematic_ayurveda_prompt(s) for s in fallback_subjects[:max_frames]]

    logger.info(f"Generating {len(scene_prompts)} ComfyUI scene visuals for topic: '{topic_data.get('subject', '')}'...")

    # 2. Check capabilities for video vs image
    caps = detect_comfyui_capabilities()
    can_video = caps.get("can_generate_video", False)
    if can_video:
        logger.info(f"[+] ComfyUI AnimateDiff video generation available! Motion model: {caps.get('motion_model')}")
    else:
        logger.info("[*] ComfyUI text-to-image mode active (generating high-res portrait stills).")

    # 3. Generate scenes
    for idx, prompt in enumerate(scene_prompts, 1):
        target_video = output_dir / f"scene_{idx}.mp4"
        target_image = output_dir / f"scene_{idx}.jpg"

        # Check existing cache
        if target_video.exists() and target_video.stat().st_size > 1000:
            logger.info(f"Reusing cached ComfyUI visual video: {target_video.name}")
            visual_paths.append(str(target_video))
            continue
        if target_image.exists() and target_image.stat().st_size > 1000:
            logger.info(f"Reusing cached ComfyUI visual image: {target_image.name}")
            visual_paths.append(str(target_image))
            continue

        generated_file: Optional[Path] = None

        # Try video first if supported
        if can_video:
            logger.info(f"Rendering ComfyUI AnimateDiff video {idx}/{len(scene_prompts)}: '{prompt[:50]}'...")
            generated_file = generate_comfyui_video(prompt, target_video)

        # Fallback to image if video not supported or video generation failed
        if not generated_file or not target_video.exists() or target_video.stat().st_size < 1000:
            logger.info(f"Rendering ComfyUI image {idx}/{len(scene_prompts)}: '{prompt[:50]}'...")
            generated_file = generate_comfyui_image(prompt, target_image)

        if generated_file and generated_file.exists() and generated_file.stat().st_size > 1000:
            visual_paths.append(str(generated_file))

    return visual_paths
