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
from typing import Dict, Any, List, Optional, Tuple, Union
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


def extract_combo_options(input_def: Any) -> List[str]:
    """
    Extracts combo/dropdown options from ComfyUI /object_info parameter definition.
    Handles both ComfyUI schema formats:
    1. Modern schema: ['COMBO', {'multiselect': False, 'options': ['v3_sd15_mm.ckpt', ...]}]
    2. Legacy schema: [['v3_sd15_mm.ckpt', ...], {'default': 'v3_sd15_mm.ckpt'}]
    """
    if not isinstance(input_def, (list, tuple)) or len(input_def) == 0:
        return []

    # Modern schema: index 1 is a dict containing 'options' list
    if len(input_def) > 1 and isinstance(input_def[1], dict) and "options" in input_def[1]:
        opts = input_def[1]["options"]
        if isinstance(opts, list):
            return [str(opt).strip() for opt in opts if str(opt).strip()]

    # Legacy schema: index 0 is a list of options
    if isinstance(input_def[0], list):
        return [str(opt).strip() for opt in input_def[0] if str(opt).strip()]

    # Fallback: index 0 is a dict containing 'options'
    if isinstance(input_def[0], dict) and "options" in input_def[0]:
        opts = input_def[0]["options"]
        if isinstance(opts, list):
            return [str(opt).strip() for opt in opts if str(opt).strip()]

    return []


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
            ckpt_def = (
                data.get("CheckpointLoaderSimple", {})
                .get("input", {})
                .get("required", {})
                .get("ckpt_name")
            )
            ckpt_list = extract_combo_options(ckpt_def)
            if ckpt_list:
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
                        models = extract_combo_options(req[p_name])
                        if models:
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
    - Automatically discovers Diffusion Transformer (DiT) Video nodes (LTX-Video, HunyuanVideo)
    - Automatically discovers ANY AnimateDiff implementation (AnimateDiff-Evolved, classic AnimateDiff)
    - Identifies all installed DiT models, motion models, and keyframe checkpoints
    - Detects video export options (VHS_VideoCombine, AnimateDiffCombine, SaveAnimatedWEBP)
    - Prioritizes DiT Image-to-Video (I2V) over legacy SD1.5 AnimateDiff
    """
    caps: Dict[str, Any] = {
        "available": False,
        "dit": False,
        "dit_nodes": [],
        "ltx_checkpoint": None,
        "hunyuan_checkpoint": None,
        "t5_model": None,
        "keyframe_checkpoint": None,
        "video_backend": None,  # "dit_ltx", "dit_hunyuan", "animatediff"
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
        "available_nodes": {},
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
            caps["available_nodes"] = all_nodes
    except Exception as e:
        logger.debug(f"Full /object_info fetch not available ({e}). Probing individual node endpoints...")

    # 2. Checkpoints Discovery
    ckpt_list: List[str] = []
    if "CheckpointLoaderSimple" in all_nodes:
        ckpt_def = (
            all_nodes["CheckpointLoaderSimple"]
            .get("input", {})
            .get("required", {})
            .get("ckpt_name")
        )
        ckpt_list = extract_combo_options(ckpt_def)
    if not ckpt_list:
        try:
            resp, _ = safe_comfyui_request("GET", "/object_info/CheckpointLoaderSimple", base_url=base_url, timeout=4)
            if resp.status_code == 200:
                ckpt_def = resp.json().get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name")
                ckpt_list = extract_combo_options(ckpt_def)
        except Exception:
            pass

    if isinstance(ckpt_list, list) and ckpt_list:
        caps["available_checkpoints"] = ckpt_list

        # Detect DiT LTX-Video checkpoints
        for ckpt in ckpt_list:
            c_low = str(ckpt).lower()
            if "ltx" in c_low and any(ext in c_low for ext in [".safetensors", ".ckpt", ".sft"]):
                caps["ltx_checkpoint"] = ckpt
                break

        # Detect DiT HunyuanVideo checkpoints
        for ckpt in ckpt_list:
            c_low = str(ckpt).lower()
            if "hunyuan" in c_low:
                caps["hunyuan_checkpoint"] = ckpt
                break

        # Detect high-tier SDXL / FLUX checkpoints for master keyframe generation
        for ckpt in ckpt_list:
            c_low = str(ckpt).lower()
            if any(k in c_low for k in ["realvis", "juggernaut", "flux", "turbo", "lightning", "phot", "epic"]):
                caps["keyframe_checkpoint"] = ckpt
                break

        for ckpt in ckpt_list:
            c_lower = str(ckpt).lower()
            if not any(k in c_lower for k in ["sdxl", "xl", "flux", "cascade", "ltx", "hunyuan"]):
                caps["sd15_checkpoint"] = ckpt
                break

        for ckpt in ckpt_list:
            if any(k in str(ckpt).lower() for k in ["sdxl", "xl", "turbo", "lightning", "flux", "real", "phot"]):
                caps["checkpoint"] = ckpt
                break

        if not caps["checkpoint"] and ckpt_list:
            caps["checkpoint"] = ckpt_list[0]
        if not caps["sd15_checkpoint"] and ckpt_list:
            caps["sd15_checkpoint"] = ckpt_list[0]
        if not caps["keyframe_checkpoint"]:
            caps["keyframe_checkpoint"] = caps.get("checkpoint") or (ckpt_list[0] if ckpt_list else None)

    # 3. Detect DiT Nodes (LTX-Video / HunyuanVideo)
    known_dit_nodes = [
        "LTXVImgToVideo",
        "LTXVImgToVideoInplace",
        "LTXVConditioning",
        "LTXVModelLoader",
        "LTXVScheduler",
        "HunyuanVideoSampler",
    ]
    detected_dit_nodes: List[str] = []
    if all_nodes:
        detected_dit_nodes = [
            k for k in all_nodes
            if any(d in k.lower() for d in ["ltxv", "ltx_video", "hunyuanvideo"])
        ]
    else:
        for node_name in known_dit_nodes:
            try:
                resp, _ = safe_comfyui_request("GET", f"/object_info/{node_name}", base_url=base_url, timeout=3)
                if resp.status_code == 200 and node_name in resp.json():
                    detected_dit_nodes.append(node_name)
                    all_nodes[node_name] = resp.json()[node_name]
            except Exception:
                pass

    caps["dit_nodes"] = detected_dit_nodes
    if detected_dit_nodes or "LTXVImgToVideo" in all_nodes:
        caps["dit"] = True

    # Check for T5 text encoder (needed for LTX-Video / FLUX text encoding)
    if "CLIPLoader" in all_nodes:
        clip_def = all_nodes["CLIPLoader"].get("input", {}).get("required", {}).get("clip_name")
        clip_opts = extract_combo_options(clip_def)
        for opt in clip_opts:
            if "t5" in str(opt).lower():
                caps["t5_model"] = opt
                break

    # 4. AnimateDiff Node Discovery (Legacy Fallback)
    known_ad_nodes = [
        "ADE_LoadAnimateDiffModel",
        "ADE_ApplyAnimateDiffModelSimple",
        "ADE_ApplyAnimateDiffModel",
        "ADE_UseEvolvedSampling",
        "ADE_AnimateDiffLoaderWithContext",
        "AnimateDiffLoader",
        "AnimateDiffLoaderV1",
        "AnimateDiffModuleLoader",
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

    # 5. Discover Motion Models across registered AnimateDiff nodes
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
                    model_choices = extract_combo_options(req[p_name])
                    for m in model_choices:
                        if m and m not in found_motion_models:
                            found_motion_models.append(m)

    caps["available_motion_models"] = found_motion_models
    if found_motion_models:
        for m in found_motion_models:
            if any(k in m.lower() for k in ["v3", "v2", "mm_sd_v15"]):
                caps["motion_model"] = m
                break
        if not caps["motion_model"]:
            caps["motion_model"] = found_motion_models[0]

    # 6. Video Export Nodes (VHS_VideoCombine, AnimateDiffCombine, SaveAnimatedWEBP)
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

    # 7. Determine Primary Video Backend & Assess Readiness
    # Priority 1: LTX-Video DiT (Theatrical-grade Image-to-Video at 24fps)
    if "LTXVImgToVideo" in (detected_dit_nodes or all_nodes) or caps.get("ltx_checkpoint"):
        caps["video_backend"] = "dit_ltx"
        caps["can_generate_video"] = True
    elif caps.get("hunyuan_checkpoint"):
        caps["video_backend"] = "dit_hunyuan"
        caps["can_generate_video"] = True
    elif caps["animatediff"] and caps["motion_model"]:
        caps["video_backend"] = "animatediff"
        caps["can_generate_video"] = True

    missing: List[str] = []
    if not caps["can_generate_video"]:
        missing.append("Neither LTX-Video DiT (LTXVImgToVideo) nor AnimateDiff motion module detected in ComfyUI registry")

    caps["missing_for_video"] = missing
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

    system_prompt = f"""You are an elite commercial documentary visual director for high-performing BBC / National Geographic health and wellness video shorts.
Your task is to generate exactly {num_scenes} vivid, photorealistic, visually crystal-clear scene prompts for an AI diffusion model (Stable Diffusion / AnimateDiff).

CRITICAL DIRECTIVES FOR PROFESSIONAL-GRADE VISUALS:
1. CONCRETE & TANGIBLE SUBJECTS ONLY:
   - Every scene MUST depict recognizable real-world foods, bright modern kitchen/dining environments, or relatable human expressions.
   - ABSOLUTELY FORBIDDEN: abstract internal organs, microscopic biological animations, cellular membranes, "metabolic sludge", glowing body energy x-rays, or unidentifiable brownish slime. Viewers must recognize the scene instantly in 0.2 seconds.

2. CHRONOLOGICAL STORYBOARD ARC (Story-Driven Pacing):
   - Scene 1 (The Habit / Foods): Appetizing, high-definition shot of the exact foods, ingredients, or morning drink mentioned in the hook (e.g. fresh glass of whole milk next to vibrant sliced citrus fruits on a bright marble kitchen counter).
   - Scene 2 (The Physical Discomfort): A relatable person experiencing physical discomfort (e.g. person sitting at breakfast table holding their stomach with a bloated expression, natural morning light).
   - Scene 3 (The Concrete Reaction): Clear physical demonstration (e.g. macro shot of milk reacting with acidic lemon juice in a clear glass container, crisp focus, studio lighting).
   - Scene 4 (The Symptom / Fatigue): Relatable human emotion (e.g. close-up of a tired person looking in a mirror rubbing their eyes, feeling sluggish).
   - Scene 5 (The Ancient Remedy): A warm, mouth-watering holistic preparation (e.g. steaming golden herbal ginger tea in a clear glass mug with fresh sliced ginger and raw honey on a sunlit wooden table).
   - Scene 6 (The Payoff / Vitality): An energized, healthy person outdoors in bright morning sunlight, smiling with genuine vitality and energy.

3. BRIGHT, HIGH-KEY NATURAL LIGHTING (NO GLOOMY CAVES):
   - Bright natural morning sunlight, clean modern aesthetic, soft warm fill light, vibrant natural colors.
   - FORBIDDEN: dark obsidian slate, pitch black backgrounds, moody caves, underexposed shadows.
   - Keep each prompt concise (20-35 words) so the diffusion model stays razor-sharp and tightly focused.
   - Strictly NO text, no typography, no watermarks, no cartoons, no 3D renders.

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
            return f"{subject.rstrip('. ')}, bright natural sunlight, photorealistic 8k, zero text."
        return subject

    # Anatomy, bacteria, gut, stomach, bloating, digestion
    if any(k in subj_lower for k in ["anatomy", "bacteria", "gut", "stomach", "digest", "intestine", "internal", "bloat", "toxic", "waste", "sludge"]):
        return (
            f"Relatable cinematic documentary photo of a person sitting at a dining table holding their stomach in visible bloating discomfort, "
            "bright natural morning daylight, clean modern dining room, crisp 8k focus, award-winning health photography, zero text."
        )
    # Cold liquids, ice water, cold drinks
    elif any(k in subj_lower for k in ["ice", "cold", "water", "extinguish", "freeze"]):
        return (
            f"Cinematic food photography of {subject}. "
            "A tall clear glass of ice water next to a fresh breakfast plate, bright morning sunlight streaming through window, "
            "crisp water droplets, clean marble countertop, professional 8k food photography, zero text."
        )
    # Vitality, smiling, healthy person
    elif any(k in subj_lower for k in ["person", "healthy", "glow", "smile", "vitality", "face"]):
        return (
            f"Cinematic portrait of an energized, glowing, healthy person representing {subject}. "
            "Radiant skin and genuine joyful smile, outdoors in lush green nature, warm golden morning sunshine, "
            "85mm portrait lens, shallow depth of field, photorealistic 8k, zero text."
        )
    # Cooking, boiling, herbs, tea, remedies, spices, meals, seeds
    elif any(k in subj_lower for k in ["cook", "pot", "tea", "meal", "herb", "spice", "ginger", "decoction", "remedy", "serve", "seed", "fennel", "milk"]):
        return (
            f"Mouth-watering cinematic close-up of {subject}. "
            "Steaming hot herbal infusion in a clear glass cup, fresh sliced ginger root and aromatic botanical spices on bright sunlit wooden table, "
            "delicate rising steam, morning sunlight, crisp vibrant colors, professional 8k food photography, zero text."
        )
    else:
        return (
            f"Bright cinematic documentary photography of {subject}. "
            "Sunlit kitchen tabletop setting, clean natural daylight, vivid colors, crisp shallow depth of field, "
            "professional 8k camera, National Geographic style, zero text."
        )


def generate_comfyui_image(
    prompt_text: str,
    output_path: Path,
    negative_prompt: Optional[str] = None,
    base_url: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    timeout_sec: int = 180,
) -> Optional[Path]:
    """Generates an image via ComfyUI REST API if running on the server."""
    if not is_comfyui_available(base_url):
        return None

    try:
        caps = detect_comfyui_capabilities(base_url)
        ckpt_name = caps.get("keyframe_checkpoint") or get_available_checkpoint(base_url) or "sd_xl_base_1.0.safetensors"
        ckpt_lower = ckpt_name.lower()

        # Determine optimal resolution and sampling parameters based on model architecture
        is_sdxl = any(k in ckpt_lower for k in ["sdxl", "xl", "turbo", "lightning", "flux", "realvis", "juggernaut"])
        if width is not None and height is not None:
            res_w, res_h = width, height
        elif is_sdxl:
            res_w, res_h = (768, 1024)  # Standard crisp 9:16 portrait keyframe (divisible by 32)
        else:
            res_w, res_h = (576, 1024)  # SD 1.5 vertical resolution

        if is_sdxl:
            if "turbo" in ckpt_lower:
                steps, cfg = 4, 1.5
            elif "lightning" in ckpt_lower:
                steps, cfg = 6, 2.0
            else:
                steps, cfg = 25, 7.0
        else:
            steps, cfg = 20, 7.0

        seed = random.randint(1, 1_000_000_000)
        client_id = str(uuid.uuid4())

        neg_text = (
            negative_prompt
            or "dark, underexposed, gloomy, black background, pitch black, obsidian, muddy, abstract, cellular, microscopic, internal organ, medical render, slime, sludge, cartoon, illustration, drawing, painting, 3d render, anime, deformed, bad anatomy, blurry, flicker, static, text, watermark, logo, lowres, noise"
        )

        prompt_graph = {
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": ckpt_name},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": res_w, "height": res_h, "batch_size": 1},
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


def probe_video_duration(video_path: Union[str, Path]) -> float:
    """Returns the duration of a video file in seconds using ffprobe."""
    vp = Path(video_path)
    if not vp.exists():
        return 6.0
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(vp),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception as e:
        logger.debug(f"ffprobe duration error on {vp.name}: {e}")
    return 6.0


def stitch_continuous_background_video(
    clip_paths: List[Union[str, Path]],
    output_path: Union[str, Path],
    target_duration: float,
    crossfade_sec: float = 1.0,
    fps: int = 30,
) -> Optional[Path]:
    """
    Blends a sequence of video clips with smooth 1-second crossfade dissolves into
    a single continuous background video matching target_duration.

    1. Standardizes all clips to 1080x1920 (9:16 portrait) at the specified fps.
    2. Chains FFmpeg `xfade` (transition=fade) filters dynamically across all clips.
    3. Trims or extends seamlessly to target_duration.
    4. Outputs a unified, unbroken MP4 background stream.
    """
    out_p = Path(output_path).resolve()
    valid_clips = [Path(c).resolve() for c in clip_paths if Path(c).exists() and Path(c).stat().st_size > 1000]

    if not valid_clips:
        logger.warning("No valid video clips to stitch.")
        return None

    if len(valid_clips) == 1:
        try:
            out_p.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                "ffmpeg", "-y",
                "-i", str(valid_clips[0]),
                "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps={fps}",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-r", str(fps),
                "-t", str(target_duration),
                str(out_p),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0 and out_p.exists() and out_p.stat().st_size > 1000:
                return out_p
        except Exception as e:
            logger.warning(f"Single clip standardization failed: {e}")
            return valid_clips[0]

    durations = [max(2.0, probe_video_duration(c)) for c in valid_clips]
    logger.info(f"Stitching {len(valid_clips)} clips with durations: {[round(d, 1) for d in durations]}s (target: {target_duration:.1f}s)")

    min_dur = min(durations)
    actual_xfade = min(crossfade_sec, min_dur * 0.45)

    filter_chains = []
    for i in range(len(valid_clips)):
        filter_chains.append(
            f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps={fps}[s{i}]"
        )

    curr_label = "s0"
    accum_dur = durations[0]
    for i in range(1, len(valid_clips)):
        offset = max(0.1, accum_dur - actual_xfade)
        next_label = f"xf{i}" if i < len(valid_clips) - 1 else "final_xf"
        filter_chains.append(
            f"[{curr_label}][s{i}]xfade=transition=fade:duration={actual_xfade:.2f}:offset={offset:.2f}[{next_label}]"
        )
        curr_label = next_label
        accum_dur = offset + durations[i]

    if accum_dur < target_duration:
        pad_dur = round(target_duration - accum_dur + 0.5, 2)
        filter_chains.append(f"[{curr_label}]tpad=stop_mode=clone:stop_duration={pad_dur}[padded]")
        curr_label = "padded"

    filter_complex = ";".join(filter_chains)

    out_p.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y"]
    for c in valid_clips:
        cmd.extend(["-i", str(c)])
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", f"[{curr_label}]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-r", str(fps),
        "-t", str(target_duration),
        str(out_p),
    ])

    try:
        logger.info(f"Executing continuous background stitching with FFmpeg ({len(valid_clips)} clips)...")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if res.returncode == 0 and out_p.exists() and out_p.stat().st_size > 1000:
            logger.info(f"[+] Successfully stitched continuous background video: {out_p.name} ({out_p.stat().st_size // 1024} KB)")
            return out_p
        else:
            logger.warning(f"FFmpeg crossfade stitch failed (code {res.returncode}): {res.stderr[:300]}")
    except Exception as e:
        logger.warning(f"Error during video stitching: {e}")

    return None


def upload_image_to_comfyui(image_path: Union[str, Path], base_url: Optional[str] = None) -> Optional[str]:
    """
    Uploads a local master keyframe image to ComfyUI via POST /upload/image.
    Returns the uploaded image filename accessible to the LoadImage node.
    """
    img_p = Path(image_path).resolve()
    if not img_p.exists() or img_p.stat().st_size < 100:
        logger.warning(f"Keyframe image not found or empty: {img_p}")
        return None

    urls = get_comfyui_base_urls(base_url)
    for u in urls:
        upload_url = f"{u}/upload/image"
        try:
            with open(img_p, "rb") as f:
                files = {"image": (img_p.name, f, "image/png")}
                data = {"overwrite": "true", "subfolder": ""}
                resp = requests.post(upload_url, files=files, data=data, timeout=30)
                if resp.status_code == 200:
                    resp_data = resp.json()
                    uploaded_name = resp_data.get("name") or img_p.name
                    logger.info(f"[+] Successfully uploaded master keyframe '{img_p.name}' to ComfyUI as '{uploaded_name}'")
                    return uploaded_name
        except Exception as e:
            logger.debug(f"Failed to upload keyframe to ComfyUI at {u}: {e}")
            continue

    return img_p.name


def generate_master_keyframe(
    prompt_text: str,
    output_path: Path,
    negative_prompt: Optional[str] = None,
    base_url: Optional[str] = None,
    width: int = 768,
    height: int = 1024,
    timeout_sec: int = 240,
) -> Optional[Path]:
    """
    Phase 1: Generates an ultra-photorealistic, high-resolution 9:16 portrait master keyframe (768x1024)
    using SDXL or FLUX.1-schnell before video motion synthesis.
    Locks in subject identity, authentic herbs, and cinematic documentary lighting.
    """
    logger.info(f"Phase 1: Generating master keyframe image ({width}x{height}): {prompt_text[:60]}...")
    return generate_comfyui_image(
        prompt_text=prompt_text,
        output_path=output_path,
        negative_prompt=negative_prompt,
        base_url=base_url,
        width=width,
        height=height,
        timeout_sec=timeout_sec,
    )


def generate_theatrical_i2v_clip(
    prompt_text: str,
    output_path: Path,
    keyframe_image: Optional[Union[str, Path]] = None,
    negative_prompt: Optional[str] = None,
    base_url: Optional[str] = None,
    num_frames: int = 97,
    frame_rate: int = 24,
    width: int = 768,
    height: int = 1024,
    timeout_sec: int = 600,
) -> Optional[Path]:
    """
    Phase 2: Generates a theatrical-grade 24fps Image-to-Video (I2V) clip using LTX-Video DiT.
    1. Ensures a locked master keyframe image exists (generates via SDXL/FLUX if not provided).
    2. Uploads the keyframe into ComfyUI's input pool.
    3. Chains LTXVImgToVideo -> KSampler -> VAEDecode -> VHS_VideoCombine.
    4. Guarantees 100% visual consistency and zero identity drift.
    """
    if not is_comfyui_available(base_url):
        return None

    # Step 1: Ensure Master Keyframe exists (Phase 1 Image Lock)
    keyframe_path: Path
    if keyframe_image and Path(keyframe_image).exists() and Path(keyframe_image).stat().st_size > 1000:
        keyframe_path = Path(keyframe_image).resolve()
        logger.info(f"Using provided master keyframe for I2V: {keyframe_path.name}")
    else:
        keyframe_path = output_path.with_name(f"{output_path.stem}_keyframe.png")
        if not keyframe_path.exists() or keyframe_path.stat().st_size < 1000:
            logger.info(f"Master keyframe missing. Generating Phase 1 image lock: '{keyframe_path.name}'...")
            gen_img = generate_master_keyframe(
                prompt_text=prompt_text,
                output_path=keyframe_path,
                negative_prompt=negative_prompt,
                base_url=base_url,
                width=width,
                height=height,
            )
            if not gen_img or not keyframe_path.exists() or keyframe_path.stat().st_size < 1000:
                logger.warning(f"Could not generate master keyframe for '{output_path.name}'")
                return None

    # Step 2: Discover ComfyUI DiT capabilities
    caps = detect_comfyui_capabilities(base_url)
    all_nodes = caps.get("available_nodes", {})
    ltx_ckpt = caps.get("ltx_checkpoint") or "ltx-video-2b-v0.9.1.safetensors"
    t5_model = caps.get("t5_model")
    export_node = caps.get("video_export_node") or "VHS_VideoCombine"

    # Step 3: Upload keyframe image to ComfyUI
    uploaded_name = upload_image_to_comfyui(keyframe_path, base_url=base_url) or keyframe_path.name

    seed = random.randint(1, 1_000_000_000)
    client_id = str(uuid.uuid4())

    motion_prompt = (
        f"{prompt_text}. Theatrical 24fps cinema, slow cinematic camera push-in, subtle natural movement, "
        "gentle steam rising, realistic fluid dynamics, crisp cinematic lighting, 8k documentary footage, photorealistic."
    )
    motion_neg = (
        negative_prompt
        or "distorted, jitter, warp, stutter, static, morphing faces, ugly, cartoon, illustration, low resolution, blurry, watermark"
    )

    # Frame count for LTX-Video must adhere to 8n + 1 (e.g. 65, 81, 97, 121)
    valid_frames = num_frames
    if (num_frames - 1) % 8 != 0:
        valid_frames = ((num_frames // 8) * 8) + 1
        logger.info(f"Adjusted frame count to LTX-Video 8n+1 requirement: {num_frames} -> {valid_frames}")

    # Step 4: Construct ComfyUI DiT Image-to-Video (I2V) Prompt Graph
    prompt_graph: Dict[str, Any] = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": uploaded_name},
        },
        "2": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ltx_ckpt},
        },
    }

    clip_ref = ["2", 1]
    if t5_model and ("CLIPLoader" in all_nodes or "CLIPLoader" in caps.get("dit_nodes", [])):
        prompt_graph["9"] = {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": t5_model, "type": "ltxv"},
        }
        clip_ref = ["9", 0]

    prompt_graph["3"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": motion_prompt, "clip": clip_ref},
    }
    prompt_graph["4"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": motion_neg, "clip": clip_ref},
    }

    # LTXVImgToVideo: injects the locked master keyframe into latent video space
    prompt_graph["5"] = {
        "class_type": "LTXVImgToVideo",
        "inputs": {
            "image": ["1", 0],
            "positive": ["3", 0],
            "negative": ["4", 0],
            "vae": ["2", 2],
            "width": width,
            "height": height,
            "length": valid_frames,
            "batch_size": 1,
            "strength": 1.0,
        },
    }

    # KSampler: 25 steps, CFG 3.0, euler sampler
    prompt_graph["6"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": 25,
            "cfg": 3.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["2", 0],
            "positive": ["5", 0],
            "negative": ["5", 1],
            "latent_image": ["5", 2],
        },
    }

    # VAEDecode using LTX VAE
    prompt_graph["7"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["6", 0], "vae": ["2", 2]},
    }

    # VideoCombine export to 24fps MP4
    if export_node == "VHS_VideoCombine":
        prompt_graph["8"] = {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["7", 0],
                "frame_rate": frame_rate,
                "loop_count": 0,
                "filename_prefix": "ayurveda_theatrical_i2v",
                "format": "video/h264-mp4",
                "pingpong": False,
                "save_output": True,
            },
        }
    elif export_node == "SaveAnimatedWEBP":
        prompt_graph["8"] = {
            "class_type": "SaveAnimatedWEBP",
            "inputs": {
                "images": ["7", 0],
                "filename_prefix": "ayurveda_theatrical_i2v",
                "fps": float(frame_rate),
                "lossless": False,
                "quality": 88,
                "method": "default",
            },
        }
    else:
        prompt_graph["8"] = {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "ayurveda_theatrical_i2v", "images": ["7", 0]},
        }

    # Step 5: Submit Prompt to ComfyUI REST API
    try:
        logger.info(
            f"Submitting Theatrical DiT I2V prompt to ComfyUI ({ltx_ckpt}, {valid_frames} frames @ {frame_rate}fps): "
            f"Keyframe='{keyframe_path.name}' -> '{prompt_text[:50]}'..."
        )
        resp, reachable_url = safe_comfyui_request(
            "POST",
            "/prompt",
            base_url=base_url,
            json={"prompt": prompt_graph, "client_id": client_id},
            timeout=10,
        )

        if resp.status_code != 200:
            logger.warning(f"ComfyUI DiT I2V prompt submission failed: {resp.status_code} - {resp.text}")
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
                                        logger.info(f"[+] Successfully generated Theatrical DiT I2V video saved to {output_path}")
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
                                        return temp_anim
            except Exception as poll_err:
                logger.debug(f"Polling ComfyUI DiT video: {poll_err}")

            time.sleep(2.5)

        logger.warning(f"ComfyUI DiT video generation timed out after {timeout_sec}s for prompt_id: {prompt_id}")
        return None
    except Exception as e:
        logger.warning(f"ComfyUI DiT video generation error: {e}")
        return None


def generate_comfyui_video(
    prompt_text: str,
    output_path: Path,
    negative_prompt: Optional[str] = None,
    base_url: Optional[str] = None,
    num_frames: int = 48,
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
        or "dark, underexposed, gloomy, black background, pitch black, obsidian, muddy, abstract, cellular, microscopic, internal organ, medical render, slime, sludge, cartoon, illustration, drawing, painting, 3d render, anime, deformed, bad anatomy, blurry, flicker, static, text, watermark, logo, lowres, noise"
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

        # ComfyUI-AnimateDiff-Evolved Gen2 node chain:
        # 1. Loader outputs MOTION_MODEL_ADE (Node 2)
        # 2. Apply node outputs M_MODELS bundle (Node 3)
        # 3. UseEvolvedSampling node patches checkpoint MODEL with M_MODELS for KSampler (Node 10)
        ad_nodes = caps.get("animatediff_nodes", [])
        if "ADE_ApplyAnimateDiffModelSimple" in ad_nodes:
            prompt_graph["3"] = {
                "class_type": "ADE_ApplyAnimateDiffModelSimple",
                "inputs": {
                    "motion_model": ["2", 0],
                },
            }
        else:
            prompt_graph["3"] = {
                "class_type": "ADE_ApplyAnimateDiffModel",
                "inputs": {
                    "motion_model": ["2", 0],
                    "start_percent": 0.0,
                    "end_percent": 1.0,
                },
            }

        # Wire ADE_StandardUniformContextOptions to enable sliding-window temporal attention for long clips (>16 frames)
        evolved_inputs: Dict[str, Any] = {
            "model": ["1", 0],
            "m_models": ["3", 0],
        }

        ctx_node = next((n for n in ["ADE_StandardUniformContextOptions", "ADE_AnimateDiffUniformContextOptions", "ADE_LoopedUniformContextOptions"] if n in ad_nodes), None)
        if num_frames > 16 and ctx_node:
            ctx_inputs: Dict[str, Any] = {
                "context_length": 16,
                "context_stride": 1,
                "context_overlap": 4,
            }
            try:
                resp, _ = safe_comfyui_request("GET", f"/object_info/{ctx_node}", base_url=base_url, timeout=3)
                if resp.status_code == 200 and ctx_node in resp.json():
                    req_spec = resp.json()[ctx_node].get("input", {}).get("required", {})
                    if "fuse_method" in req_spec:
                        f_opts = extract_combo_options(req_spec["fuse_method"])
                        ctx_inputs["fuse_method"] = f_opts[0] if f_opts else "flat"
            except Exception:
                pass

            prompt_graph["11"] = {
                "class_type": ctx_node,
                "inputs": ctx_inputs,
            }

            ctx_key = "context_options"
            try:
                resp, _ = safe_comfyui_request("GET", "/object_info/ADE_UseEvolvedSampling", base_url=base_url, timeout=3)
                if resp.status_code == 200 and "ADE_UseEvolvedSampling" in resp.json():
                    u_inputs = {
                        **resp.json()["ADE_UseEvolvedSampling"].get("input", {}).get("required", {}),
                        **resp.json()["ADE_UseEvolvedSampling"].get("input", {}).get("optional", {}),
                    }
                    if "context_options" in u_inputs:
                        ctx_key = "context_options"
                    elif "context_opts" in u_inputs:
                        ctx_key = "context_opts"
            except Exception:
                pass
            evolved_inputs[ctx_key] = ["11", 0]

        # Query ADE_UseEvolvedSampling beta_schedule options
        beta_schedule = "autoselect"
        try:
            resp, _ = safe_comfyui_request("GET", "/object_info/ADE_UseEvolvedSampling", base_url=base_url, timeout=3)
            if resp.status_code == 200 and "ADE_UseEvolvedSampling" in resp.json():
                node_spec = resp.json()["ADE_UseEvolvedSampling"]
                b_opts = extract_combo_options(node_spec.get("input", {}).get("required", {}).get("beta_schedule"))
                if b_opts:
                    for pref in ["autoselect", "sqrt_linear (AnimateDiff)", "sqrt_linear", "linear"]:
                        match = next((opt for opt in b_opts if pref.lower() in str(opt).lower()), None)
                        if match:
                            beta_schedule = match
                            break
                    else:
                        beta_schedule = b_opts[0]
        except Exception:
            pass

        evolved_inputs["beta_schedule"] = beta_schedule

        prompt_graph["10"] = {
            "class_type": "ADE_UseEvolvedSampling",
            "inputs": evolved_inputs,
        }
        model_ref = ["10", 0]
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


def free_comfyui_memory(base_url: Optional[str] = None) -> bool:
    """Tells ComfyUI to unload models from VRAM and free memory."""
    try:
        resp, _ = safe_comfyui_request(
            "POST",
            "/free",
            base_url=base_url,
            json={"unload_models": True, "free_memory": True},
            timeout=5,
        )
        if resp.status_code == 200:
            logger.info("[+] Freed ComfyUI VRAM models.")
            return True
    except Exception as e:
        logger.debug(f"Could not free ComfyUI memory: {e}")
    return False


def generate_scene_visuals(
    topic_data: Dict[str, Any],
    output_dir: Path,
    queries: Optional[List[str]] = None,
    script_json: Optional[Dict[str, Any]] = None,
    max_frames: int = 5,
    num_frames: int = 97,
    frame_rate: int = 24,
) -> List[str]:
    """
    Generates theatrical AI visual frames or video clips for the video scenes via ComfyUI.
    Uses contextual LLM prompts from the full narrative script when available.
    Strictly prioritizes Image-to-Video (I2V) DiT synthesis (LTX-Video / HunyuanVideo)
    at 24fps with zero identity drift, with graceful fallback to SDXL keyframes.
    Returns list of saved visual file paths (.mp4 or .jpg/.png).
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

    # Free all Ollama LLM models from GPU VRAM completely so ComfyUI has maximum memory for DiT video
    try:
        from common.ollama_client import unload_all_ollama_models
        unload_all_ollama_models()
    except Exception:
        pass

    # 2. Check capabilities for DiT vs legacy AnimateDiff vs still image
    caps = detect_comfyui_capabilities()
    backend = caps.get("video_backend")
    can_video = caps.get("can_generate_video", False)
    is_dit = (backend in ["dit_ltx", "dit_hunyuan"] or caps.get("dit", False))

    if is_dit:
        logger.info(f"[+] ComfyUI Theatrical DiT Video engine active! Model: {caps.get('ltx_checkpoint') or 'LTX-Video 2B'}")
    elif can_video:
        logger.info(f"[+] ComfyUI AnimateDiff video generation available! Motion model: {caps.get('motion_model')}")
    else:
        missing_reasons = "; ".join(caps.get("missing_for_video", [])) or "No video nodes detected"
        logger.info(f"[*] ComfyUI master keyframe still image mode active. [Video disabled: {missing_reasons}]")

    # 3. Generate scenes (Strict Image-First -> Video Synthesis)
    for idx, prompt in enumerate(scene_prompts, 1):
        target_video = output_dir / f"scene_{idx}.mp4"
        keyframe_png = output_dir / f"scene_{idx}_keyframe.png"
        target_image = output_dir / f"scene_{idx}.jpg"

        # Check existing cache
        if target_video.exists() and target_video.stat().st_size > 1000:
            logger.info(f"Reusing cached ComfyUI visual video: {target_video.name}")
            visual_paths.append(str(target_video))
            continue
        if not can_video and keyframe_png.exists() and keyframe_png.stat().st_size > 1000:
            logger.info(f"Reusing cached ComfyUI master keyframe: {keyframe_png.name}")
            visual_paths.append(str(keyframe_png))
            continue
        if not can_video and target_image.exists() and target_image.stat().st_size > 1000:
            logger.info(f"Reusing cached ComfyUI visual image: {target_image.name}")
            visual_paths.append(str(target_image))
            continue

        generated_file: Optional[Path] = None

        # Priority 1: Theatrical DiT Image-to-Video Synthesis (LTX-Video @ 24fps)
        if is_dit:
            logger.info(f"Rendering Theatrical DiT I2V video {idx}/{len(scene_prompts)} ({num_frames} frames @ {frame_rate}fps): '{prompt[:50]}'...")
            generated_file = generate_theatrical_i2v_clip(
                prompt_text=prompt,
                output_path=target_video,
                keyframe_image=keyframe_png,
                num_frames=num_frames,
                frame_rate=frame_rate,
                width=768,
                height=1024,
            )
        # Priority 2: Legacy AnimateDiff Fallback
        elif can_video:
            logger.info(f"Rendering ComfyUI AnimateDiff video {idx}/{len(scene_prompts)} ({num_frames} frames @ {frame_rate}fps): '{prompt[:50]}'...")
            generated_file = generate_comfyui_video(
                prompt,
                target_video,
                num_frames=min(48, num_frames),
                frame_rate=min(12, frame_rate),
            )

        # Fallback: Master keyframe image if video failed or unsupported
        if not generated_file or not target_video.exists() or target_video.stat().st_size < 1000:
            if keyframe_png.exists() and keyframe_png.stat().st_size > 1000:
                logger.info(f"Using generated master keyframe still {idx}/{len(scene_prompts)}: '{keyframe_png.name}'")
                generated_file = keyframe_png
            else:
                logger.info(f"Rendering ComfyUI master keyframe image {idx}/{len(scene_prompts)}: '{prompt[:50]}'...")
                generated_file = generate_master_keyframe(prompt, keyframe_png, width=768, height=1024)
                if not generated_file or not keyframe_png.exists():
                    generated_file = generate_comfyui_image(prompt, target_image)

        if generated_file and generated_file.exists() and generated_file.stat().st_size > 1000:
            visual_paths.append(str(generated_file))

    # Free ComfyUI models from VRAM after generation batch completes
    try:
        free_comfyui_memory()
    except Exception:
        pass

    return visual_paths


def diagnose_comfyui(base_url: Optional[str] = None):
    """Prints a comprehensive diagnostic report of ComfyUI DiT & Video capabilities and registered nodes."""
    print("\n" + "=" * 68)
    print("      ComfyUI DiT (LTX-Video) & Video Capabilities Diagnostic Report")
    print("=" * 68)

    avail, msg, reachable = check_comfyui_connection(base_url)
    print(f"Server Connection: {'[+] ONLINE' if avail else '[-] OFFLINE'}")
    print(f"Active Endpoint:   {reachable or 'None'}")
    print(f"Status Details:    {msg}\n")

    if not avail:
        print("[!] ComfyUI server is unreachable. Please verify ComfyUI is running:")
        print("    python main.py --listen 0.0.0.0 --port 8188 --highvram")
        print("=" * 68 + "\n")
        return

    caps = detect_comfyui_capabilities(reachable)

    print("1. THEATRICAL DiT VIDEO NODES REGISTERED:")
    for node in caps.get("dit_nodes", []):
        print(f"   * {node}")
    if not caps.get("dit_nodes"):
        print("   [-] No DiT custom nodes detected (LTXVImgToVideo, LTXVConditioning).")

    print("\n2. DiT & MASTER KEYFRAME CHECKPOINTS (models/checkpoints/):")
    for ckpt in caps.get("available_checkpoints", []):
        tags = []
        if ckpt == caps.get("ltx_checkpoint"):
            tags.append("[ACTIVE LTX-VIDEO DiT]")
        if ckpt == caps.get("keyframe_checkpoint"):
            tags.append("[MASTER KEYFRAME]")
        if ckpt == caps.get("sd15_checkpoint"):
            tags.append("[SD1.5 FALLBACK]")
        tag_str = f"  --> {' '.join(tags)}" if tags else ""
        print(f"   * {ckpt}{tag_str}")
    if not caps.get("available_checkpoints"):
        print("   [-] None detected in models/checkpoints/")

    print(f"\n3. T5 TEXT ENCODER: {caps.get('t5_model') or 'None detected (will use checkpoint CLIP)'}")

    print("\n4. ANIMATEDIFF MOTION MODULES (LEGACY FALLBACK):")
    for mm in caps.get("available_motion_models", []):
        tag = "  --> [SELECTED ACTIVE]" if mm == caps.get("motion_model") else ""
        print(f"   * {mm}{tag}")
    if not caps.get("available_motion_models"):
        print("   [-] No AnimateDiff motion models found.")

    export_node = caps.get("video_export_node")
    print(f"\n5. VIDEO / ANIMATION EXPORT NODE: {export_node}")
    if export_node == "VHS_VideoCombine":
        print("   [+] Native 24fps MP4 export enabled via VideoHelperSuite.")
    elif export_node in ["SaveAnimatedWEBP", "AnimateDiffCombine"]:
        print(f"   [+] Animation export enabled via {export_node} (auto-converts to MP4 with ffmpeg).")
    else:
        print("   [*] Frame export fallback active.")

    print(f"\n6. ACTIVE VIDEO BACKEND: {caps.get('video_backend') or 'None (still image mode)'}")
    print(f"   Readiness: {'[+] READY FOR 24FPS THEATRICAL DiT VIDEO' if caps.get('video_backend') == 'dit_ltx' else '[*] READY (Fallback Mode)' if caps.get('can_generate_video') else '[-] NOT READY (Still image mode only)'}")

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
