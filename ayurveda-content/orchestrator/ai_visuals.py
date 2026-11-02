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
import subprocess
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
                for ckpt in ckpt_list:
                    if any(k in ckpt.lower() for k in ["sdxl", "xl", "turbo", "lightning", "flux", "real", "phot"]):
                        return ckpt
                return ckpt_list[0]
    except Exception as e:
        logger.debug(f"Failed to fetch checkpoint info from ComfyUI: {e}")
    return None


def get_available_motion_model(base_url: Optional[str] = None) -> Optional[str]:
    """Discovers available AnimateDiff motion models installed in ComfyUI across known loader nodes."""
    candidate_nodes = [
        "ADE_LoadAnimateDiffModel",
        "ADE_AnimateDiffLoaderWithContext",
        "AnimateDiffLoader",
        "AnimateDiffLoaderV1",
        "AnimateDiffModuleLoader",
    ]
    for node_name in candidate_nodes:
        try:
            resp, _ = safe_comfyui_request("GET", f"/object_info/{node_name}", base_url=base_url, timeout=4)
            if resp.status_code == 200:
                data = resp.json().get(node_name, {})
                req = data.get("input", {}).get("required", {})
                for p_name in ["model_name", "motion_model", "motion_module", "animatediff_model"]:
                    if p_name in req:
                        models = req[p_name][0]
                        if models and isinstance(models, list) and len(models) > 0:
                            for m in models:
                                if any(k in str(m).lower() for k in ["v3", "v2", "mm_sd_v15"]):
                                    return str(m)
                            return str(models[0])
        except Exception:
            continue
    return None


def detect_comfyui_capabilities(base_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Comprehensive discovery of ComfyUI capabilities:
    - Automatically discovers ANY AnimateDiff implementation (AnimateDiff-Evolved, classic AnimateDiff, etc.)
    - Identifies all installed motion models from any model directory
    - Detects video export options (VHS_VideoCombine, AnimateDiffCombine, SaveAnimatedWEBP)
    - Automatically falls back to core animated WebP/GIF when VHS is absent
    """
    caps: Dict[str, Any] = {
        "available": False,
        "animatediff": False,
        "animatediff_nodes": [],
        "animatediff_loader_node": None,
        "vhs": False,
        "video_export_node": None,
        "svd": False,
        "can_generate_video": False,
        "motion_model": None,
        "available_motion_models": [],
        "checkpoint": None,
        "sd15_checkpoint": None,
        "available_checkpoints": [],
        "missing_for_video": [],
    }

    if not is_comfyui_available(base_url):
        return caps

    caps["available"] = True

    # 1. Fetch full node catalog if available
    all_nodes: Dict[str, Any] = {}
    try:
        resp, reachable_endpoint = safe_comfyui_request("GET", "/object_info", base_url=base_url, timeout=6)
        if resp.status_code == 200 and isinstance(resp.json(), dict):
            all_nodes = resp.json()
    except Exception as e:
        logger.debug(f"Full /object_info fetch not available ({e}). Probing individual node endpoints...")

    # 2. Checkpoints
    ckpt_list: List[str] = []
    if "CheckpointLoaderSimple" in all_nodes:
        ckpt_list = (
            all_nodes["CheckpointLoaderSimple"]
            .get("input", {})
            .get("required", {})
            .get("ckpt_name", [[]])[0]
        )
    if not ckpt_list:
        try:
            resp, _ = safe_comfyui_request("GET", "/object_info/CheckpointLoaderSimple", base_url=base_url, timeout=4)
            if resp.status_code == 200:
                ckpt_list = resp.json().get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
        except Exception:
            pass

    if isinstance(ckpt_list, list) and ckpt_list:
        caps["available_checkpoints"] = ckpt_list
        for ckpt in ckpt_list:
            c_lower = str(ckpt).lower()
            if not any(k in c_lower for k in ["sdxl", "xl", "flux", "cascade"]):
                caps["sd15_checkpoint"] = ckpt
                break
        for ckpt in ckpt_list:
            if any(k in str(ckpt).lower() for k in ["sdxl", "xl", "turbo", "lightning", "flux", "real", "phot"]):
                caps["checkpoint"] = ckpt
                break
        if not caps["checkpoint"]:
            caps["checkpoint"] = ckpt_list[0]
        if not caps["sd15_checkpoint"]:
            caps["sd15_checkpoint"] = ckpt_list[0]

    # 3. AnimateDiff Node Discovery
    known_ad_nodes = [
        "ADE_LoadAnimateDiffModel",
        "ADE_AnimateDiffLoaderWithContext",
        "AnimateDiffLoader",
        "AnimateDiffLoaderV1",
        "AnimateDiffModuleLoader",
        "ADE_ApplyAnimateDiffModel",
        "AnimateDiffCombine",
    ]

    detected_ad_nodes: List[str] = []
    if all_nodes:
        detected_ad_nodes = [
            k for k in all_nodes
            if "animatediff" in k.lower() or k.startswith("ADE_")
        ]
    else:
        for node_name in known_ad_nodes:
            try:
                resp, _ = safe_comfyui_request("GET", f"/object_info/{node_name}", base_url=base_url, timeout=3)
                if resp.status_code == 200 and node_name in resp.json():
                    detected_ad_nodes.append(node_name)
                    all_nodes[node_name] = resp.json()[node_name]
            except Exception:
                pass

    caps["animatediff_nodes"] = detected_ad_nodes
    if detected_ad_nodes:
        caps["animatediff"] = True

    # Identify primary loader node
    for candidate in [
        "ADE_LoadAnimateDiffModel",
        "ADE_AnimateDiffLoaderWithContext",
        "AnimateDiffLoader",
        "AnimateDiffLoaderV1",
        "AnimateDiffModuleLoader",
    ]:
        if candidate in detected_ad_nodes:
            caps["animatediff_loader_node"] = candidate
            break

    # 4. Discover Motion Models across any registered AnimateDiff node
    found_motion_models: List[str] = []
    for node_name in (detected_ad_nodes or known_ad_nodes):
        node_info = all_nodes.get(node_name)
        if not node_info:
            try:
                resp, _ = safe_comfyui_request("GET", f"/object_info/{node_name}", base_url=base_url, timeout=3)
                if resp.status_code == 200 and node_name in resp.json():
                    node_info = resp.json()[node_name]
            except Exception:
                pass
        if node_info:
            req = node_info.get("input", {}).get("required", {})
            for p_name in ["model_name", "motion_model", "motion_module", "animatediff_model"]:
                if p_name in req:
                    model_choices = req[p_name][0]
                    if isinstance(model_choices, list):
                        for m in model_choices:
                            m_str = str(m).strip()
                            if m_str and m_str not in found_motion_models:
                                found_motion_models.append(m_str)

    caps["available_motion_models"] = found_motion_models
    if found_motion_models:
        for m in found_motion_models:
            if any(k in m.lower() for k in ["v3", "v2", "mm_sd_v15"]):
                caps["motion_model"] = m
                break
        if not caps["motion_model"]:
            caps["motion_model"] = found_motion_models[0]

    # 5. Video Export Nodes (VHS_VideoCombine, AnimateDiffCombine, SaveAnimatedWEBP)
    for v_node in ["VHS_VideoCombine", "AnimateDiffCombine", "SaveAnimatedWEBP", "SaveAnimatedPNG"]:
        if v_node in all_nodes:
            if v_node == "VHS_VideoCombine":
                caps["vhs"] = True
            if not caps["video_export_node"]:
                caps["video_export_node"] = v_node
        else:
            try:
                resp, _ = safe_comfyui_request("GET", f"/object_info/{v_node}", base_url=base_url, timeout=3)
                if resp.status_code == 200 and v_node in resp.json():
                    if v_node == "VHS_VideoCombine":
                        caps["vhs"] = True
                    if not caps["video_export_node"]:
                        caps["video_export_node"] = v_node
            except Exception:
                pass

    if not caps["video_export_node"]:
        caps["video_export_node"] = "SaveImage"

    # 6. Assess Readiness & Formulate Diagnostics
    missing: List[str] = []
    if not caps["animatediff"]:
        missing.append("No AnimateDiff custom nodes detected in ComfyUI registry")
    elif not caps["motion_model"]:
        misplaced = [c for c in caps.get("available_checkpoints", []) if any(k in str(c).lower() for k in ["v3", "v2", "mm_sd", "animatediff"])]
        if misplaced:
            missing.append(
                f"Motion model '{misplaced[0]}' was found in models/checkpoints/, but AnimateDiff expects it in ComfyUI/models/animatediff_models/ (or custom_nodes/ComfyUI-AnimateDiff/models/). Copy or symlink it there."
            )
        else:
            missing.append(
                f"AnimateDiff node '{caps.get('animatediff_loader_node') or 'AnimateDiff'}' is installed, but no motion model (.ckpt/.safetensors) was found in ComfyUI/models/animatediff_models/."
            )

    caps["missing_for_video"] = missing

    # Capable of generating video as long as AnimateDiff is present and a motion model is loaded!
    if caps["animatediff"] and caps["motion_model"]:
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


def convert_animation_to_mp4(src_path: Path, dst_mp4: Path) -> bool:
    """Converts an animated WebP, GIF, or image sequence to H.264 MP4 using system ffmpeg."""
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(src_path),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            str(dst_mp4),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        return res.returncode == 0 and dst_mp4.exists() and dst_mp4.stat().st_size > 1000
    except Exception as e:
        logger.debug(f"ffmpeg conversion error: {e}")
        return False


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
    Generates a 9:16 short video clip via ComfyUI AnimateDiff.
    Automatically adapts to whichever AnimateDiff loader node is installed
    (ADE_LoadAnimateDiffModel, ADE_AnimateDiffLoaderWithContext, AnimateDiffLoader, etc.)
    and whichever video/animation export node is available (VHS_VideoCombine, AnimateDiffCombine, SaveAnimatedWEBP).
    """
    if not is_comfyui_available(base_url):
        return None

    caps = detect_comfyui_capabilities(base_url)
    if not caps.get("can_generate_video"):
        missing_str = "; ".join(caps.get("missing_for_video", []))
        logger.debug(f"ComfyUI video generation skipped ({missing_str}).")
        return None

    ckpt_name = caps.get("sd15_checkpoint") or caps.get("checkpoint")
    motion_model = caps.get("motion_model") or get_available_motion_model(base_url)

    if not ckpt_name or not motion_model:
        logger.warning(f"Missing required models for video: ckpt={ckpt_name}, motion_model={motion_model}")
        return None

    loader_node = caps.get("animatediff_loader_node") or "ADE_LoadAnimateDiffModel"
    export_node = caps.get("video_export_node") or "VHS_VideoCombine"

    seed = random.randint(1, 1_000_000_000)
    client_id = str(uuid.uuid4())
    neg_text = (
        negative_prompt
        or "text, watermark, logo, font, subtitle, cartoon, illustration, drawing, painting, bad anatomy, deformed, blurry, static, flicker"
    )

    # 512x768 is the optimal 9:16 portrait resolution for SD1.5 AnimateDiff
    width, height = 512, 768
    steps, cfg = 20, 7.0

    prompt_graph: Dict[str, Any] = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ckpt_name},
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
    }

    # Inject AnimateDiff based on detected loader node variant
    model_ref = ["1", 0]
    if loader_node == "ADE_LoadAnimateDiffModel":
        prompt_graph["2"] = {
            "class_type": "ADE_LoadAnimateDiffModel",
            "inputs": {"model_name": motion_model},
        }
        prompt_graph["3"] = {
            "class_type": "ADE_ApplyAnimateDiffModel",
            "inputs": {
                "model": ["1", 0],
                "motion_model": ["2", 0],
            },
        }
        model_ref = ["3", 0]
    elif loader_node == "ADE_AnimateDiffLoaderWithContext":
        prompt_graph["3"] = {
            "class_type": "ADE_AnimateDiffLoaderWithContext",
            "inputs": {
                "model": ["1", 0],
                "model_name": motion_model,
                "beta_schedule": "sqrt_linear (default)",
            },
        }
        model_ref = ["3", 0]
    else:
        # Classic AnimateDiffLoader / AnimateDiffLoaderV1
        prompt_graph["3"] = {
            "class_type": loader_node,
            "inputs": {
                "model": ["1", 0],
                "model_name": motion_model,
                "latents": ["4", 0],
            },
        }
        model_ref = ["3", 0]

    # KSampler and VAEDecode
    prompt_graph["7"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": "euler_ancestral",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": model_ref,
            "positive": ["5", 0],
            "negative": ["6", 0],
            "latent_image": ["4", 0],
        },
    }
    prompt_graph["8"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["7", 0], "vae": ["1", 2]},
    }

    # Video combine / animation export node
    if export_node == "VHS_VideoCombine":
        prompt_graph["9"] = {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["8", 0],
                "frame_rate": frame_rate,
                "loop_count": 0,
                "filename_prefix": "ayurveda_anim",
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            },
        }
    elif export_node == "AnimateDiffCombine":
        prompt_graph["9"] = {
            "class_type": "AnimateDiffCombine",
            "inputs": {
                "images": ["8", 0],
                "frame_rate": frame_rate,
                "loop_count": 0,
                "save_image": True,
                "filename_prefix": "ayurveda_anim",
                "format": "image/gif",
            },
        }
    elif export_node == "SaveAnimatedWEBP":
        prompt_graph["9"] = {
            "class_type": "SaveAnimatedWEBP",
            "inputs": {
                "images": ["8", 0],
                "filename_prefix": "ayurveda_anim",
                "fps": float(frame_rate),
                "lossless": False,
                "quality": 85,
                "method": "default",
            },
        }
    else:
        prompt_graph["9"] = {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "ayurveda_anim", "images": ["8", 0]},
        }

    try:
        logger.info(f"Submitting AnimateDiff video prompt to ComfyUI ({loader_node} + {motion_model}, {export_node}): {prompt_text[:60]}...")
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
                                    file_ext = Path(filename).suffix.lower()
                                    if file_ext in [".mp4", ".mov", ".m4v"]:
                                        with open(output_path, "wb") as f:
                                            f.write(v_resp.content)
                                        logger.info(f"[+] Successfully generated ComfyUI video saved to {output_path}")
                                        return output_path
                                    elif file_ext in [".webp", ".gif"]:
                                        temp_anim = output_path.with_suffix(file_ext)
                                        with open(temp_anim, "wb") as f:
                                            f.write(v_resp.content)
                                        if convert_animation_to_mp4(temp_anim, output_path):
                                            try:
                                                temp_anim.unlink()
                                            except Exception:
                                                pass
                                            logger.info(f"[+] Converted ComfyUI animated {file_ext} to MP4: {output_path}")
                                            return output_path
                                        else:
                                            logger.info(f"[+] Saved ComfyUI animated visual to {temp_anim}")
                                            return temp_anim
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
        missing_reasons = "; ".join(caps.get("missing_for_video", [])) or "No video nodes detected"
        logger.info(f"[*] ComfyUI text-to-image mode active (generating high-res portrait stills). [Video disabled: {missing_reasons}]")

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


def diagnose_comfyui(base_url: Optional[str] = None):
    """Prints a comprehensive diagnostic report of ComfyUI capabilities and registered nodes."""
    print("\n" + "=" * 68)
    print("      ComfyUI AnimateDiff & Video Capabilities Diagnostic Report")
    print("=" * 68)

    avail, msg, reachable = check_comfyui_connection(base_url)
    print(f"Server Connection: {'[+] ONLINE' if avail else '[-] OFFLINE'}")
    print(f"Active Endpoint:   {reachable or 'None'}")
    print(f"Status Details:    {msg}\n")

    if not avail:
        print("[!] ComfyUI server is unreachable. Please verify ComfyUI is running:")
        print("    python main.py --listen 0.0.0.0 --port 8188")
        print("=" * 68 + "\n")
        return

    caps = detect_comfyui_capabilities(reachable)

    print("1. CHECKPOINTS DETECTED (models/checkpoints/):")
    for ckpt in caps.get("available_checkpoints", []):
        tag = "  --> [ACTIVE SD1.5]" if ckpt == caps.get("sd15_checkpoint") else ""
        print(f"   * {ckpt}{tag}")
    if not caps.get("available_checkpoints"):
        print("   [-] None detected in models/checkpoints/")

    print("\n2. ANIMATEDIFF NODES REGISTERED IN COMFYUI:")
    for node in caps.get("animatediff_nodes", []):
        tag = "  --> [PRIMARY LOADER]" if node == caps.get("animatediff_loader_node") else ""
        print(f"   * {node}{tag}")
    if not caps.get("animatediff_nodes"):
        print("   [-] No AnimateDiff custom nodes detected in ComfyUI registry.")

    print("\n3. MOTION MODELS DETECTED:")
    for mm in caps.get("available_motion_models", []):
        tag = "  --> [SELECTED ACTIVE]" if mm == caps.get("motion_model") else ""
        print(f"   * {mm}{tag}")
    if not caps.get("available_motion_models"):
        print("   [-] No motion models found in AnimateDiff model directories.")

    export_node = caps.get("video_export_node")
    print(f"\n4. VIDEO / ANIMATION EXPORT NODE: {export_node}")
    if export_node == "VHS_VideoCombine":
        print("   [+] Native MP4 export enabled via VideoHelperSuite.")
    elif export_node in ["SaveAnimatedWEBP", "AnimateDiffCombine"]:
        print(f"   [+] Animation export enabled via {export_node} (auto-converts to MP4 with ffmpeg).")
    else:
        print("   [*] Frame export fallback active.")

    print(f"\n5. VIDEO GENERATION READINESS: {'[+] READY (Can generate AnimateDiff video clips)' if caps.get('can_generate_video') else '[-] NOT READY (Still image mode only)'}")

    if caps.get("missing_for_video"):
        print("\nDIAGNOSTIC ADVISORY:")
        for m in caps["missing_for_video"]:
            print(f"   [!] {m}")

    print("=" * 68 + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ComfyUI Diagnostic & Visuals Generator")
    parser.add_argument("--diagnose", action="store_true", default=True, help="Diagnose ComfyUI capabilities")
    args = parser.parse_args()
    diagnose_comfyui()
