#!/usr/bin/env python3
"""
Cinematic Media Director & Asset Manager
Fetches, caches, and grades real high-resolution documentary imagery
for corporate warfare & psychological narrative videos.

Architecture:
1. Primary: Pexels API (if PEXELS_API_KEY is configured in .env)
2. Secondary: Wikimedia Commons API (100% free, zero-config, CC0/Public Domain)
3. Local Cache: Preserves downloaded assets in narrative_warfare/assets/cache/
4. Cinematic Post-Processing: 1080x1920 9:16 vertical crop, film noir color grading,
   shadow depth adjustment, and soft vignette for maximum caption legibility.
"""

import os
import re
import io
import math
import random
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

import requests
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from narrative_warfare.visual_generator import (
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    apply_dynamic_vignette,
    render_scene_backdrop as render_procedural_fallback,
)

logger = logging.getLogger("media_director")

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "assets" / "cache"

# Scene keyword mappings designed specifically for corporate warfare & narrative psychology
SCENE_SEARCH_PROFILES = {
    "HOOK": [
        "Manhattan skyline night financial district",
        "Wall Street New York dark skyscrapers",
        "corporate office glass building night",
        "financial district city lights dramatic night",
    ],
    "CHESSBOARD": [
        "modern boardroom glass conference table",
        "corporate executive boardroom meeting room",
        "high rise office interior looking out night",
        "corporate skyscraper architecture glass facade",
    ],
    "ORDERBOOK": [
        "trading floor Frankfurt stock exchange",
        "New York Stock Exchange trading floor interior",
        "financial market trading terminal monitors",
        "stock exchange floor brokers trading",
    ],
    "TAKEOVER": [
        "skyscrapers financial district London night",
        "Tokyo financial district night skyline",
        "dramatic skyscraper tower night lights",
        "bank headquarters building facade dusk",
    ],
}


# -----------------------------------------------------------------------------
# Image Fetchers (Pexels + Wikimedia Commons)
# -----------------------------------------------------------------------------
def fetch_pexels_image(query: str, api_key: str) -> Optional[Image.Image]:
    """Queries Pexels API for curated vertical (portrait) commercial-grade photography."""
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": "portrait",
        "per_page": 5,
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            photos = data.get("photos", [])
            if photos:
                # Pick a random photo from the top results for visual variance
                chosen = random.choice(photos[:3])
                img_url = chosen.get("src", {}).get("large2x") or chosen.get("src", {}).get("portrait")
                if img_url:
                    img_resp = requests.get(img_url, timeout=15)
                    if img_resp.status_code == 200:
                        return Image.open(io.BytesIO(img_resp.content)).convert("RGB")
    except Exception as e:
        logger.warning(f"Pexels fetch error for query '{query}': {e}")
    return None


def fetch_wikimedia_image(query: str) -> Optional[Image.Image]:
    """
    Queries Wikimedia Commons API for high-resolution public domain / CC0 imagery.
    Zero-config, completely free, no API key required.
    """
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "format": "json",
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 1280,
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NarrativeWarfareBot/1.0"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for pid, p in pages.items():
                ii = p.get("imageinfo", [{}])[0]
                img_url = ii.get("thumburl") or ii.get("url")
                if img_url:
                    clean_url = img_url.split("?")[0]
                    if clean_url.lower().endswith((".jpg", ".jpeg", ".png")):
                        img_resp = requests.get(clean_url, headers=headers, timeout=15)
                        if img_resp.status_code == 200 and len(img_resp.content) > 15000:
                            return Image.open(io.BytesIO(img_resp.content)).convert("RGB")
    except Exception as e:
        logger.warning(f"Wikimedia fetch error for query '{query}': {e}")
    return None


# -----------------------------------------------------------------------------
# Cinematic Post-Processing (9:16 Aspect + Color Grade)
# -----------------------------------------------------------------------------
def process_cinematic_vertical(
    img: Image.Image,
    palette: Dict[str, Any],
    target_w: int = CANVAS_WIDTH,
    target_h: int = CANVAS_HEIGHT,
) -> Image.Image:
    """
    Converts raw stock photography into an elite, moody 1080x1920 documentary backdrop:
    - Smart center crop to 9:16 vertical aspect ratio
    - Noir contrast enhancement (1.30x)
    - Controlled dimming (0.62x) so subtitle cards have high contrast
    - Temperature color shift matching the session's visual seed
    - Radial vignette mask
    """
    w, h = img.size
    target_ratio = target_w / target_h
    img_ratio = w / h

    if img_ratio > target_ratio:
        # Image is wider: center crop width
        new_w = int(h * target_ratio)
        left = max(0, (w - new_w) // 2)
        cropped = img.crop((left, 0, left + new_w, h))
    else:
        # Image is taller: center crop height
        new_h = int(w / target_ratio)
        top = max(0, (h - new_h) // 2)
        cropped = img.crop((0, top, w, top + new_h))

    resized = cropped.resize((target_w, target_h), Image.Resampling.BILINEAR)

    # 1. Darken background slightly to prioritize subtitle contrast
    bright_enhancer = ImageEnhance.Brightness(resized)
    darkened = bright_enhancer.enhance(0.60)

    # 2. Boost contrast for dramatic documentary lighting
    contrast_enhancer = ImageEnhance.Contrast(darkened)
    contrasted = contrast_enhancer.enhance(1.28)

    # 3. Apply subtle temperature shift based on palette
    arr = np.array(contrasted, dtype=np.float32)
    tr, tg, tb = palette.get("temp_shift", (1.0, 1.0, 1.0))
    arr[:, :, 0] = np.clip(arr[:, :, 0] * tr, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] * tg, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] * tb, 0, 255)
    tinted = Image.fromarray(arr.astype(np.uint8))

    # 4. Apply cinematic radial vignette
    vignetted = apply_dynamic_vignette(
        tinted,
        radius_factor=palette.get("vignette_radius", 0.65),
        strength=palette.get("vignette_strength", 0.75),
    )

    return vignetted


# -----------------------------------------------------------------------------
# Orchestrated Scene Backdrop Dispatcher
# -----------------------------------------------------------------------------
def get_cinematic_scene_backdrop(
    scene_type: str,
    palette: Dict[str, Any],
    topic: str,
    seed: int,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> np.ndarray:
    """
    Returns a high-resolution 1080x1920 (9:16) cinematic background array for the scene.
    Checks local cache first, attempts online stock fetch, falls back to procedural noir.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"scene_{scene_type.lower()}_{seed % 10}.jpg"

    # 1. Check local cache
    if cache_file.exists():
        try:
            cached_img = Image.open(str(cache_file)).convert("RGB")
            logger.info(f"[MEDIA DIRECTOR] Loaded cached backdrop for scene '{scene_type}': {cache_file.name}")
            return np.array(process_cinematic_vertical(cached_img, palette))
        except Exception as e:
            logger.warning(f"Failed to load cached image {cache_file}: {e}")

    # 2. Build contextual search queries
    profile_queries = SCENE_SEARCH_PROFILES.get(scene_type, SCENE_SEARCH_PROFILES["HOOK"])
    rng = random.Random(seed + hash(scene_type))
    selected_query = rng.choice(profile_queries)

    pexels_key = os.getenv("PEXELS_API_KEY", "").strip()
    raw_img: Optional[Image.Image] = None

    # 3. Attempt Pexels (if API key present)
    if pexels_key:
        logger.info(f"[MEDIA DIRECTOR] Fetching Pexels stock for scene '{scene_type}' (query: '{selected_query}')...")
        raw_img = fetch_pexels_image(selected_query, pexels_key)

    # 4. Attempt Wikimedia Commons (zero-config fallback)
    if raw_img is None:
        logger.info(f"[MEDIA DIRECTOR] Fetching Wikimedia stock for scene '{scene_type}' (query: '{selected_query}')...")
        raw_img = fetch_wikimedia_image(selected_query)

    # 5. Process & save to cache
    if raw_img is not None:
        try:
            raw_img.save(str(cache_file), quality=92)
            logger.info(f"[MEDIA DIRECTOR] Saved new stock asset to cache: {cache_file.name}")
            graded = process_cinematic_vertical(raw_img, palette)
            return np.array(graded)
        except Exception as e:
            logger.warning(f"Error caching/processing stock image: {e}")

    # 6. Fallback to procedural noir
    logger.info(f"[MEDIA DIRECTOR] Using procedural noir fallback for scene '{scene_type}'.")
    return render_procedural_fallback(scene_type, palette, topic, seed)
