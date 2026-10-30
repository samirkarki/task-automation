#!/usr/bin/env python3
"""
Unified Stock Video & Media Provider (Pexels, Pixabay, Wikimedia, & Curated CC0 Fallbacks)
Allows searching and downloading portrait (9:16) stock media assets.
Works with zero API keys out-of-the-box by leveraging curated CC0 nature & wellness video assets.
"""

import logging
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import requests

from common.env_loader import load_project_env

load_project_env()

logger = logging.getLogger("common.stock_media")

# Curated High-Definition CC0 Public Domain Vertical Wellness / Nature Video URLs
# These serve as instant, zero-key fallbacks so anyone can test and render immediately!
CURATED_CC0_WELLNESS_VIDEOS = [
    # 1. Warm Herbal Tea / Pouring Water
    "https://assets.mixkit.co/videos/preview/mixkit-hot-tea-poured-into-a-cup-42898-large.mp4",
    # 2. Relaxing Nature Meditation / Sunlight Trees
    "https://assets.mixkit.co/videos/preview/mixkit-sun-rays-shining-through-the-branches-of-a-tree-42528-large.mp4",
    # 3. Forest River / Flowing Water
    "https://assets.mixkit.co/videos/preview/mixkit-river-stream-in-the-forest-42527-large.mp4",
    # 4. Spices & Botanical Herbs Mortar
    "https://assets.mixkit.co/videos/preview/mixkit-mortar-and-pestle-with-herbs-and-spices-41525-large.mp4",
    # 5. Peaceful Night Sky / Sleep
    "https://assets.mixkit.co/videos/preview/mixkit-night-sky-with-stars-and-clouds-42531-large.mp4",
]


class PexelsClient:
    """Client for Pexels Video and Photo API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("PEXELS_API_KEY", "").strip()

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def search_videos(
        self,
        query: str,
        orientation: str = "portrait",
        per_page: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search Pexels for stock videos matching query and orientation."""
        if not self.is_available:
            return []

        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": self.api_key}
        params = {"query": query, "orientation": orientation, "per_page": per_page}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=12)
            if resp.status_code == 200:
                return resp.json().get("videos", [])
        except Exception as e:
            logger.warning(f"Pexels query failed: {e}")
        return []

    def download_video(
        self,
        query: str,
        output_dir: Path,
        target_filename: Optional[str] = None,
        orientation: str = "portrait",
    ) -> Optional[Path]:
        videos = self.search_videos(query=query, orientation=orientation, per_page=5)
        if not videos:
            return None

        chosen = videos[0]
        v_files = chosen.get("video_files", [])

        target_vf = None
        for vf in v_files:
            h = vf.get("height", 0)
            w = vf.get("width", 0)
            if orientation == "portrait" and (h >= 1080 or (h >= 720 and h > w)):
                target_vf = vf
                break

        if not target_vf and v_files:
            target_vf = v_files[0]

        if not target_vf or not target_vf.get("link"):
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        fname = target_filename or f"pexels_{chosen['id']}.mp4"
        out_file = output_dir / fname

        if out_file.exists() and out_file.stat().st_size > 50000:
            return out_file

        try:
            dl_resp = requests.get(target_vf["link"], stream=True, timeout=40)
            if dl_resp.status_code == 200:
                with open(out_file, "wb") as f:
                    for chunk in dl_resp.iter_content(chunk_size=1024 * 64):
                        f.write(chunk)
                return out_file
        except Exception as e:
            logger.warning(f"Failed downloading Pexels video: {e}")

        return None


class PixabayClient:
    """Client for Pixabay Video API (free instant API key)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("PIXABAY_API_KEY", "").strip()

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def search_videos(self, query: str) -> List[Dict[str, Any]]:
        if not self.is_available:
            return []
        url = "https://pixabay.com/api/videos/"
        params = {
            "key": self.api_key,
            "q": query,
            "video_type": "all",
            "per_page": 5,
        }
        try:
            r = requests.get(url, params=params, timeout=12)
            if r.status_code == 200:
                return r.json().get("hits", [])
        except Exception as e:
            logger.warning(f"Pixabay video search error: {e}")
        return []

    def download_video(self, query: str, output_dir: Path, target_filename: Optional[str] = None) -> Optional[Path]:
        hits = self.search_videos(query)
        if not hits:
            return None
        chosen = hits[0]
        vids = chosen.get("videos", {})
        # Pick medium or large
        target = vids.get("medium") or vids.get("large") or vids.get("small")
        if not target or not target.get("url"):
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        fname = target_filename or f"pixabay_{chosen['id']}.mp4"
        out_file = output_dir / fname

        if out_file.exists() and out_file.stat().st_size > 50000:
            return out_file

        try:
            r = requests.get(target["url"], stream=True, timeout=40)
            if r.status_code == 200:
                with open(out_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 64):
                        f.write(chunk)
                return out_file
        except Exception as e:
            logger.warning(f"Failed downloading Pixabay video: {e}")
        return None


def download_curated_cc0_video(index: int, output_dir: Path, target_filename: Optional[str] = None) -> Optional[Path]:
    """Downloads a royalty-free CC0 public wellness video (zero API key required)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    url = CURATED_CC0_WELLNESS_VIDEOS[index % len(CURATED_CC0_WELLNESS_VIDEOS)]
    fname = target_filename or f"cc0_wellness_{index + 1}.mp4"
    out_file = output_dir / fname

    if out_file.exists() and out_file.stat().st_size > 50000:
        return out_file

    logger.info(f"Downloading zero-key CC0 wellness clip ({index + 1}/{len(CURATED_CC0_WELLNESS_VIDEOS)})...")
    try:
        r = requests.get(url, stream=True, timeout=30)
        if r.status_code == 200:
            with open(out_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    f.write(chunk)
            logger.info(f"[+] Downloaded CC0 clip: {out_file.name}")
            return out_file
    except Exception as e:
        logger.warning(f"Could not download CC0 clip from {url}: {e}")
    return None


def download_batch_stock_videos(
    queries: List[str],
    output_dir: Union[str, Path],
    orientation: str = "portrait",
) -> List[Path]:
    """
    Downloads stock videos with smart fallback order:
    1. Pexels (if PEXELS_API_KEY is present)
    2. Pixabay (if PIXABAY_API_KEY is present)
    3. Curated zero-key CC0 wellness clips (works out of the box with 0 keys!)
    """
    out_p = Path(output_dir).resolve()
    out_p.mkdir(parents=True, exist_ok=True)

    pexels = PexelsClient()
    pixabay = PixabayClient()

    downloaded: List[Path] = []
    for idx, q in enumerate(queries, 1):
        target_name = f"clip_{idx}.mp4"
        clip_path = None

        # 1. Try Pexels if configured
        if pexels.is_available:
            clip_path = pexels.download_video(q, out_p, target_filename=target_name, orientation=orientation)

        # 2. Try Pixabay if configured
        if not clip_path and pixabay.is_available:
            clip_path = pixabay.download_video(q, out_p, target_filename=target_name)

        # 3. Fallback to Curated Free CC0 Wellness Videos (Zero-Key)
        if not clip_path:
            clip_path = download_curated_cc0_video(idx - 1, out_p, target_filename=target_name)

        if clip_path:
            downloaded.append(clip_path)

    return downloaded
