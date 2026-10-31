#!/usr/bin/env python3
"""
Pluggable Visual Media Provider Architecture
Allows swapping, chaining, or combining different visual generation backends:
1. Pixabay (Live-action stock MP4 videos & high-res photos - free API key)
2. Local SDXL Turbo (PyTorch + Diffusers on Nvidia L4 GPU - zero keys, 100% offline)
3. ComfyUI (Local or remote ComfyUI REST endpoint)
4. Pexels (Stock videos & photos)
5. Wikimedia Commons (Zero-config free CC0 public domain photography)
6. Procedural Noir (Zero-dependency emergency fallback)

Extensibility:
To add a new provider (e.g. Fal.ai, Replicate, Midjourney, Leonardo, Runway),
simply inherit from BaseVisualProvider and register it with the VisualProviderRegistry.
"""

import os
import io
import re
import json
import time
import random
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import requests
import numpy as np
from PIL import Image, ImageEnhance

from narrative_warfare.env_loader import load_project_env

# Guarantee environment variables from .env are loaded
load_project_env()

from narrative_warfare.visual_generator import (
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    apply_dynamic_vignette,
    render_scene_backdrop as render_procedural_canvas,
)

logger = logging.getLogger("visual_providers")

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "assets" / "cache"


@dataclass
class VisualAsset:
    """Represents a resolved visual asset for a video beat."""
    file_path: Path
    media_type: str  # "video" or "image"
    source_provider: str
    duration: float = 0.0  # Duration in seconds if video


def extract_concise_keywords(text: str) -> List[str]:
    """
    Transforms multi-word descriptive phrases into punchy 1-2 word tags
    optimized for stock video and photo APIs.
    Stock search engines (Pixabay, Pexels) perform strict AND matching,
    so long sentences return 0 hits.
    """
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower()).strip()
    stop_words = {
        "and", "the", "for", "with", "from", "that", "this", "these", "those",
        "photo", "cinematic", "video", "footage", "shot", "showing", "view",
        "dramatic", "modern", "luxury", "classified", "dark", "moody"
    }
    words = [w for w in clean.split() if len(w) > 2 and w not in stop_words]

    candidates = []
    # 1. First two key terms
    if len(words) >= 2:
        candidates.append(f"{words[0]} {words[1]}")
    # 2. Single primary term
    if words:
        candidates.append(words[0])
    # 3. Full clean string if short
    if len(clean.split()) <= 3 and clean not in candidates:
        candidates.append(clean)

    # 4. Curated high-yield corporate warfare / finance fallbacks
    fallbacks = [
        "stock market",
        "boardroom",
        "skyscraper",
        "trading",
        "businessman",
        "city night",
        "finance",
    ]
    for fb in fallbacks:
        if fb not in candidates:
            candidates.append(fb)

    return candidates


class BaseVisualProvider(ABC):
    """Abstract Base Class for all pluggable visual media providers."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if required credentials, endpoints, or local libraries are present."""
        pass

    @abstractmethod
    def fetch_visual(
        self,
        search_query: str,
        ai_prompt: str,
        media_preference: str,  # "video" | "image" | "any"
        palette: Dict[str, Any],
        seed: int,
        output_dir: Path,
    ) -> Optional[VisualAsset]:
        """Fetches or generates a visual asset. Returns None if unable to fulfill."""
        pass


# -----------------------------------------------------------------------------
# 1. Pixabay Visual Provider (Live-Action Stock Video & Photos)
# -----------------------------------------------------------------------------
class PixabayVisualProvider(BaseVisualProvider):
    name = "pixabay"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("PIXABAY_API_KEY", "").strip()

    def is_available(self) -> bool:
        # Dynamically refresh from environment
        if not self.api_key:
            self.api_key = os.getenv("PIXABAY_API_KEY", "").strip()
        return bool(self.api_key)

    def fetch_visual(
        self,
        search_query: str,
        ai_prompt: str,
        media_preference: str,
        palette: Dict[str, Any],
        seed: int,
        output_dir: Path,
    ) -> Optional[VisualAsset]:
        if not self.is_available():
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        candidates = extract_concise_keywords(search_query)

        # 1. Attempt Video fetch first if preference is "video" or "any"
        if media_preference in ("video", "any"):
            video_asset = self._fetch_video(candidates, output_dir, seed)
            if video_asset:
                return video_asset

        # 2. Fallback to Pixabay Photo
        photo_asset = self._fetch_photo(candidates, output_dir, palette, seed)
        if photo_asset:
            return photo_asset

        return None

    def _fetch_video(self, candidates: List[str], output_dir: Path, seed: int) -> Optional[VisualAsset]:
        url = "https://pixabay.com/api/videos/"
        for query in candidates:
            params = {
                "key": self.api_key,
                "q": query,
                "video_type": "all",
                "safesearch": "true",
                "per_page": 10,
            }
            try:
                r = requests.get(url, params=params, timeout=10)
                if r.status_code == 200:
                    hits = r.json().get("hits", [])
                    if hits:
                        chosen = random.Random(seed).choice(hits[:min(5, len(hits))])
                        videos = chosen.get("videos", {})
                        # Prefer medium (1280x720) or large (1920x1080) for fast download
                        v_info = videos.get("medium") or videos.get("large") or videos.get("small")
                        if v_info and v_info.get("url"):
                            v_url = v_info["url"]
                            cache_file = output_dir / f"pixabay_vid_{chosen['id']}.mp4"
                            if not cache_file.exists() or cache_file.stat().st_size < 50000:
                                vr = requests.get(v_url, timeout=30)
                                if vr.status_code == 200 and len(vr.content) > 50000:
                                    with open(cache_file, "wb") as f:
                                        f.write(vr.content)

                            if cache_file.exists() and cache_file.stat().st_size > 50000:
                                duration = float(chosen.get("duration", 5))
                                logger.info(
                                    f"[PIXABAY] Downloaded stock video for '{query}': "
                                    f"{cache_file.name} ({duration:.1f}s, {cache_file.stat().st_size // 1024} KB)"
                                )
                                return VisualAsset(
                                    file_path=cache_file,
                                    media_type="video",
                                    source_provider=self.name,
                                    duration=duration,
                                )
            except Exception as e:
                logger.warning(f"[PIXABAY] Video search error for candidate '{query}': {e}")
                continue

        return None

    def _fetch_photo(self, candidates: List[str], output_dir: Path, palette: Dict[str, Any], seed: int) -> Optional[VisualAsset]:
        url = "https://pixabay.com/api/"
        for query in candidates:
            # First try vertical, then fallback to all orientations (which get auto-cropped)
            for orientation in ("vertical", "all"):
                params = {
                    "key": self.api_key,
                    "q": query,
                    "image_type": "photo",
                    "orientation": orientation,
                    "safesearch": "true",
                    "per_page": 8,
                }
                try:
                    r = requests.get(url, params=params, timeout=10)
                    if r.status_code == 200:
                        hits = r.json().get("hits", [])
                        if hits:
                            chosen = random.Random(seed).choice(hits[:min(4, len(hits))])
                            img_url = chosen.get("largeImageURL") or chosen.get("webformatURL")
                            if img_url:
                                cache_file = output_dir / f"pixabay_img_{chosen['id']}.jpg"
                                if not cache_file.exists():
                                    ir = requests.get(img_url, timeout=15)
                                    if ir.status_code == 200 and len(ir.content) > 10000:
                                        raw_img = Image.open(io.BytesIO(ir.content)).convert("RGB")
                                        graded = self._grade_vertical(raw_img, palette)
                                        graded.save(cache_file, quality=92)

                                if cache_file.exists() and cache_file.stat().st_size > 10000:
                                    logger.info(f"[PIXABAY] Processed stock photo for '{query}': {cache_file.name}")
                                    return VisualAsset(file_path=cache_file, media_type="image", source_provider=self.name)
                except Exception as e:
                    logger.warning(f"[PIXABAY] Photo search error for candidate '{query}': {e}")
                    continue

        return None

    @staticmethod
    def _grade_vertical(img: Image.Image, palette: Dict[str, Any]) -> Image.Image:
        w, h = img.size
        target_ratio = CANVAS_WIDTH / CANVAS_HEIGHT
        if (w / h) > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            cropped = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            cropped = img.crop((0, top, w, top + new_h))
        resized = cropped.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.BILINEAR)
        dimmed = ImageEnhance.Brightness(resized).enhance(0.72)
        contrasted = ImageEnhance.Contrast(dimmed).enhance(1.24)
        return apply_dynamic_vignette(contrasted)


# -----------------------------------------------------------------------------
# 2. Local SDXL Turbo Provider (PyTorch + Diffusers on Nvidia L4)
# -----------------------------------------------------------------------------
class LocalSDXLVisualProvider(BaseVisualProvider):
    name = "local_sdxl"

    def __init__(self, model_id: str = "stabilityai/sdxl-turbo"):
        self.model_id = model_id
        self._pipe = None

    def is_available(self) -> bool:
        if os.getenv("ENABLE_LOCAL_SDXL", "true").lower() in ("0", "false", "no"):
            return False
        try:
            import torch
            import diffusers
            return torch.cuda.is_available()
        except ImportError:
            return False

    def _init_pipeline(self):
        if self._pipe is None:
            import torch
            from diffusers import AutoPipelineForText2Image
            logger.info(f"[LOCAL SDXL] Loading pipeline '{self.model_id}' onto CUDA...")
            self._pipe = AutoPipelineForText2Image.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16,
                variant="fp16",
            ).to("cuda")

    def fetch_visual(
        self,
        search_query: str,
        ai_prompt: str,
        media_preference: str,
        palette: Dict[str, Any],
        seed: int,
        output_dir: Path,
    ) -> Optional[VisualAsset]:
        if not self.is_available():
            return None

        prompt = (
            ai_prompt.strip()
            or f"cinematic dark corporate warfare photo of {search_query}, 35mm film, 8k, photorealistic"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        cache_file = output_dir / f"sdxl_{abs(hash(prompt)) % 100000}_{seed}.jpg"

        if cache_file.exists():
            return VisualAsset(file_path=cache_file, media_type="image", source_provider=self.name)

        try:
            self._init_pipeline()
            import torch
            generator = torch.Generator("cuda").manual_seed(seed)
            logger.info(f"[LOCAL SDXL] Generating 1080x1920 frame for prompt: '{prompt[:60]}...'")

            # SDXL Turbo is optimized for 1-4 steps at 512-1024 base resolution
            gen_img = self._pipe(
                prompt=prompt,
                num_inference_steps=2,
                guidance_scale=0.0,
                width=576,
                height=1024,
                generator=generator,
            ).images[0]

            resized = gen_img.resize((CANVAS_WIDTH, CANVAS_HEIGHT), Image.Resampling.BILINEAR)
            dimmed = ImageEnhance.Brightness(resized).enhance(0.70)
            contrasted = ImageEnhance.Contrast(dimmed).enhance(1.22)
            final_img = apply_dynamic_vignette(contrasted)
            final_img.save(cache_file, quality=92)

            return VisualAsset(file_path=cache_file, media_type="image", source_provider=self.name)
        except Exception as e:
            logger.warning(f"[LOCAL SDXL] Inference error: {e}")
            return None


# -----------------------------------------------------------------------------
# 3. ComfyUI Provider (Local or Remote ComfyUI REST Endpoint)
# -----------------------------------------------------------------------------
class ComfyUIProvider(BaseVisualProvider):
    name = "comfyui"

    def __init__(self, endpoint: Optional[str] = None):
        self.endpoint = (endpoint or os.getenv("COMFYUI_URL", "http://0.0.0.0:8188/")).strip().rstrip("/")

    def _get_candidate_endpoints(self) -> List[str]:
        raw = self.endpoint
        endpoints = [raw]
        if "0.0.0.0" in raw:
            endpoints.append(raw.replace("0.0.0.0", "127.0.0.1"))
        elif "127.0.0.1" in raw:
            endpoints.append(raw.replace("127.0.0.1", "0.0.0.0"))
        return endpoints

    def is_available(self) -> bool:
        if os.getenv("ENABLE_COMFYUI", "true").lower() == "false":
            return False
        for ep in self._get_candidate_endpoints():
            try:
                r = requests.get(f"{ep}/system_stats", timeout=2)
                if r.status_code == 200:
                    return True
            except Exception:
                continue
        return False

    def fetch_visual(
        self,
        search_query: str,
        ai_prompt: str,
        media_preference: str,
        palette: Dict[str, Any],
        seed: int,
        output_dir: Path,
    ) -> Optional[VisualAsset]:
        if not self.is_available():
            return None

        prompt = (
            ai_prompt.strip()
            or f"cinematic dark corporate warfare photo of {search_query}, 35mm film, 8k, photorealistic"
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        cache_file = output_dir / f"comfy_{abs(hash(prompt)) % 100000}_{seed}.jpg"
        if cache_file.exists() and cache_file.stat().st_size > 1000:
            return VisualAsset(file_path=cache_file, media_type="image", source_provider=self.name)

        try:
            import importlib.util
            ai_vis_path = Path(__file__).resolve().parent.parent / "ayurveda-content" / "orchestrator" / "ai_visuals.py"
            if ai_vis_path.exists():
                spec = importlib.util.spec_from_file_location("ayurveda_ai_visuals", ai_vis_path)
                if spec and spec.loader:
                    ai_vis = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(ai_vis)
                    res = ai_vis.generate_comfyui_image(prompt_text=prompt, output_path=cache_file, base_url=self.endpoint)
                    if res and cache_file.exists() and cache_file.stat().st_size > 1000:
                        return VisualAsset(file_path=cache_file, media_type="image", source_provider=self.name)
        except Exception as e:
            logger.debug(f"[COMFYUI] fetch_visual error: {e}")

        return None


# -----------------------------------------------------------------------------
# 4. Pexels Provider (Stock Videos & Photos)
# -----------------------------------------------------------------------------
class PexelsVisualProvider(BaseVisualProvider):
    name = "pexels"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("PEXELS_API_KEY", "").strip()

    def is_available(self) -> bool:
        if not self.api_key:
            self.api_key = os.getenv("PEXELS_API_KEY", "").strip()
        return bool(self.api_key)

    def fetch_visual(
        self,
        search_query: str,
        ai_prompt: str,
        media_preference: str,
        palette: Dict[str, Any],
        seed: int,
        output_dir: Path,
    ) -> Optional[VisualAsset]:
        if not self.is_available():
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        candidates = extract_concise_keywords(search_query)

        # 1. Attempt Video fetch first if preference is "video" or "any"
        if media_preference in ("video", "any"):
            video_asset = self._fetch_video(candidates, output_dir, seed)
            if video_asset:
                return video_asset

        # 2. Fallback to Pexels Photo
        return self._fetch_photo(candidates, output_dir, palette, seed)

    def _fetch_video(self, candidates: List[str], output_dir: Path, seed: int) -> Optional[VisualAsset]:
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": self.api_key}
        for query in candidates:
            params = {"query": query, "orientation": "portrait", "per_page": 6}
            try:
                r = requests.get(url, headers=headers, params=params, timeout=10)
                if r.status_code == 200:
                    videos = r.json().get("videos", [])
                    if videos:
                        chosen = random.Random(seed).choice(videos[:min(3, len(videos))])
                        v_files = chosen.get("video_files", [])
                        # Prefer HD files (720p or 1080p)
                        target_file = None
                        for vf in v_files:
                            if vf.get("width", 0) >= 720 or vf.get("height", 0) >= 720:
                                target_file = vf
                                break
                        if not target_file and v_files:
                            target_file = v_files[0]

                        if target_file and target_file.get("link"):
                            cache_file = output_dir / f"pexels_vid_{chosen['id']}.mp4"
                            if not cache_file.exists() or cache_file.stat().st_size < 50000:
                                vr = requests.get(target_file["link"], timeout=30)
                                if vr.status_code == 200 and len(vr.content) > 50000:
                                    with open(cache_file, "wb") as f:
                                        f.write(vr.content)

                            if cache_file.exists() and cache_file.stat().st_size > 50000:
                                duration = float(chosen.get("duration", 5))
                                logger.info(f"[PEXELS] Downloaded stock video for '{query}': {cache_file.name}")
                                return VisualAsset(
                                    file_path=cache_file,
                                    media_type="video",
                                    source_provider=self.name,
                                    duration=duration,
                                )
            except Exception as e:
                logger.warning(f"[PEXELS] Video search error for candidate '{query}': {e}")
                continue
        return None

    def _fetch_photo(self, candidates: List[str], output_dir: Path, palette: Dict[str, Any], seed: int) -> Optional[VisualAsset]:
        url = "https://api.pexels.com/v1/search"
        headers = {"Authorization": self.api_key}
        for query in candidates:
            params = {"query": query, "orientation": "portrait", "per_page": 5}
            try:
                r = requests.get(url, headers=headers, params=params, timeout=10)
                if r.status_code == 200:
                    photos = r.json().get("photos", [])
                    if photos:
                        chosen = random.Random(seed).choice(photos[:3])
                        img_url = chosen.get("src", {}).get("large2x") or chosen.get("src", {}).get("portrait")
                        if img_url:
                            cache_file = output_dir / f"pexels_img_{chosen['id']}.jpg"
                            if not cache_file.exists():
                                ir = requests.get(img_url, timeout=15)
                                if ir.status_code == 200 and len(ir.content) > 10000:
                                    raw_img = Image.open(io.BytesIO(ir.content)).convert("RGB")
                                    graded = PixabayVisualProvider._grade_vertical(raw_img, palette)
                                    graded.save(cache_file, quality=92)

                            if cache_file.exists() and cache_file.stat().st_size > 10000:
                                logger.info(f"[PEXELS] Downloaded stock photo for '{query}': {cache_file.name}")
                                return VisualAsset(file_path=cache_file, media_type="image", source_provider=self.name)
            except Exception as e:
                logger.warning(f"[PEXELS] Photo search error for candidate '{query}': {e}")
                continue
        return None


# -----------------------------------------------------------------------------
# 5. Wikimedia Commons Provider (Zero-Config Free CC0 Photography)
# -----------------------------------------------------------------------------
class WikimediaVisualProvider(BaseVisualProvider):
    name = "wikimedia"

    def is_available(self) -> bool:
        return True  # Zero-config public API

    def fetch_visual(
        self,
        search_query: str,
        ai_prompt: str,
        media_preference: str,
        palette: Dict[str, Any],
        seed: int,
        output_dir: Path,
    ) -> Optional[VisualAsset]:
        output_dir.mkdir(parents=True, exist_ok=True)
        candidates = extract_concise_keywords(search_query)

        url = "https://commons.wikimedia.org/w/api.php"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TaskAutomation/1.0"}

        for query in candidates:
            clean_name = f"wiki_{abs(hash(query)) % 100000}_{seed}.jpg"
            cache_file = output_dir / clean_name
            if cache_file.exists() and cache_file.stat().st_size > 10000:
                return VisualAsset(file_path=cache_file, media_type="image", source_provider=self.name)

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
            try:
                r = requests.get(url, params=params, headers=headers, timeout=10)
                if r.status_code == 200:
                    pages = r.json().get("query", {}).get("pages", {})
                    for pid, p in pages.items():
                        ii = p.get("imageinfo", [{}])[0]
                        img_url = ii.get("thumburl") or ii.get("url")
                        if img_url:
                            clean_url = img_url.split("?")[0]
                            if clean_url.lower().endswith((".jpg", ".jpeg", ".png")):
                                ir = requests.get(clean_url, headers=headers, timeout=12)
                                if ir.status_code == 200 and len(ir.content) > 15000:
                                    raw_img = Image.open(io.BytesIO(ir.content)).convert("RGB")
                                    graded = PixabayVisualProvider._grade_vertical(raw_img, palette)
                                    graded.save(cache_file, quality=92)
                                    logger.info(f"[WIKIMEDIA] Cached CC0 photo for '{query}': {cache_file.name}")
                                    return VisualAsset(file_path=cache_file, media_type="image", source_provider=self.name)
            except Exception as e:
                logger.warning(f"[WIKIMEDIA] Fetch error for candidate '{query}': {e}")
                continue

        return None


# -----------------------------------------------------------------------------
# 6. Procedural Noir Provider (Zero-Dependency Emergency Fallback)
# -----------------------------------------------------------------------------
class ProceduralNoirProvider(BaseVisualProvider):
    name = "procedural"

    def is_available(self) -> bool:
        return True

    def fetch_visual(
        self,
        search_query: str,
        ai_prompt: str,
        media_preference: str,
        palette: Dict[str, Any],
        seed: int,
        output_dir: Path,
    ) -> Optional[VisualAsset]:
        output_dir.mkdir(parents=True, exist_ok=True)
        cache_file = output_dir / f"procedural_{seed}.jpg"
        if not cache_file.exists():
            scenes = ["HOOK", "CHESSBOARD", "ORDERBOOK", "TAKEOVER"]
            scene_type = scenes[seed % len(scenes)]
            arr = render_procedural_canvas(scene_type, palette, search_query, seed)
            img = Image.fromarray(arr)
            img.save(cache_file, quality=90)
        return VisualAsset(file_path=cache_file, media_type="image", source_provider=self.name)


# -----------------------------------------------------------------------------
# Pluggable Provider Registry & Dispatcher
# -----------------------------------------------------------------------------
class VisualProviderRegistry:
    """
    Central registry that manages pluggable visual media providers.
    Allows configuring custom priority chains or swapping backends seamlessly.
    """

    def __init__(self):
        self._providers: Dict[str, BaseVisualProvider] = {}
        # Register standard default providers
        self.register(PixabayVisualProvider())
        self.register(LocalSDXLVisualProvider())
        self.register(ComfyUIProvider())
        self.register(PexelsVisualProvider())
        self.register(WikimediaVisualProvider())
        self.register(ProceduralNoirProvider())

    def register(self, provider: BaseVisualProvider):
        """Pluggable registration: registers any new provider instance."""
        self._providers[provider.name] = provider
        logger.debug(f"Registered visual provider: '{provider.name}'")

    def get_provider(self, name: str) -> Optional[BaseVisualProvider]:
        return self._providers.get(name)

    def list_available_providers(self) -> List[str]:
        return [name for name, p in self._providers.items() if p.is_available()]

    def resolve_visual_beat(
        self,
        search_query: str,
        ai_prompt: str,
        media_preference: str = "any",
        palette: Optional[Dict[str, Any]] = None,
        seed: int = 42,
        output_dir: Path = DEFAULT_CACHE_DIR,
        provider_preference: Optional[List[str]] = None,
    ) -> VisualAsset:
        """
        Orchestrates visual asset retrieval across the pluggable provider chain.
        Tries providers in priority order until an asset is successfully resolved.
        """
        active_palette = palette or {
            "base_bg": (12, 14, 18),
            "accent": (245, 158, 11),
            "highlight": (255, 214, 10),
            "temp_shift": (1.05, 1.0, 0.92),
            "vignette_radius": 0.65,
            "vignette_strength": 0.8,
        }

        # Determine provider chain from preference or env var
        chain_names = provider_preference
        if not chain_names:
            env_chain = os.getenv("VISUAL_PROVIDERS", "pixabay,local_sdxl,pexels,wikimedia,procedural")
            chain_names = [name.strip() for name in env_chain.split(",") if name.strip()]

        for p_name in chain_names:
            provider = self._providers.get(p_name)
            if provider and provider.is_available():
                try:
                    asset = provider.fetch_visual(
                        search_query=search_query,
                        ai_prompt=ai_prompt,
                        media_preference=media_preference,
                        palette=active_palette,
                        seed=seed,
                        output_dir=output_dir,
                    )
                    if asset and asset.file_path.exists() and asset.file_path.stat().st_size > 5000:
                        return asset
                except Exception as e:
                    logger.warning(f"Provider '{p_name}' failed to resolve visual: {e}. Trying next in chain.")

        # Final guarantee fallback
        fallback = self._providers["procedural"]
        return fallback.fetch_visual(search_query, ai_prompt, "image", active_palette, seed, output_dir)


# Global singleton instance
visual_registry = VisualProviderRegistry()
