#!/usr/bin/env python3
"""
Cinematic Media Director & Pluggable Scene Orchestrator
Plans sentence-by-sentence visual beats (every 2.5-3.8s) and resolves
visual assets (video clips / photorealistic images) across pluggable providers:
- Pixabay (Live-action stock MP4 video clips & photos)
- Local SDXL Turbo (PyTorch + Diffusers on Nvidia L4 GPU)
- ComfyUI REST endpoint
- Pexels (Stock videos/photos)
- Wikimedia Commons (Zero-config free CC0 photography)
- Procedural Noir (Fallback)

Extensibility:
Pluggable via narrative_warfare.visual_providers.visual_registry.
"""

import os
import re
import math
import random
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import numpy as np
from PIL import Image

from narrative_warfare.env_loader import load_project_env

# Guarantee environment variables from .env are loaded
load_project_env()

from narrative_warfare.visual_generator import CANVAS_WIDTH, CANVAS_HEIGHT
from narrative_warfare.visual_providers import (
    visual_registry,
    VisualAsset,
    DEFAULT_CACHE_DIR,
)

logger = logging.getLogger("media_director")


@dataclass
class VisualBeat:
    """Represents a 2.5 - 3.8 second visual cut aligned with spoken speech."""
    index: int
    start_time: float
    end_time: float
    text_snippet: str
    search_query: str
    ai_prompt: str
    media_preference: str  # "video" | "image" | "any"
    asset: Optional[VisualAsset] = None

    @property
    def duration(self) -> float:
        return max(0.5, self.end_time - self.start_time)


# -----------------------------------------------------------------------------
# Contextual Keyword & Semantic Query Extractor
# -----------------------------------------------------------------------------
SEMANTIC_PATTERNS = [
    (
        r"\b(liquid|cash|flow|bankrupt|insolvent|money|fund|credit|debt)\b",
        "stock market",
        "cinematic photo of glowing financial trading screens in dark room, stock chart analysis, 35mm film",
    ),
    (
        r"\b(raider|hostile|takeover|predat|exploit|steal|starve|weapon)\b",
        "boardroom",
        "cinematic film still of shadowy businessman in glass penthouse office overlooking night city, volumetric smoke",
    ),
    (
        r"\b(desperat|stress|vulnerab|panic|poor decision|fear)\b",
        "stressed businessman",
        "moody cinematic portrait of exhausted executive stressed at dark mahogany desk, dramatic rim lighting",
    ),
    (
        r"\b(warfare|calculat|strategy|strateg|chess|tactic|maneuver)\b",
        "chess",
        "dramatic close up of wooden chess pieces with fallen king, cinematic noir shadow lighting",
    ),
    (
        r"\b(price|sell|asset|billion|million|shares|stock|equity)\b",
        "bank vault",
        "cinematic photo of heavy steel bank vault with golden bars, dramatic spotlight, dark luxury finance thriller",
    ),
    (
        r"\b(executive|ceo|board|management|company|corporat)\b",
        "skyscraper",
        "cinematic 8k shot of illuminated financial skyscraper tower at dusk, cold steel blue reflection",
    ),
]


def extract_contextual_visual_intent(text_snippet: str, index: int) -> Tuple[str, str, str]:
    """
    Analyzes spoken sentence snippet and extracts:
    (search_query, ai_prompt, media_preference)
    Alternates media preference ('video' vs 'image') for dynamic pacing.
    """
    clean = text_snippet.lower()

    # Match semantic patterns
    for pattern, query, prompt in SEMANTIC_PATTERNS:
        if re.search(pattern, clean):
            pref = "video" if index % 2 == 0 else "image"
            return query, prompt, pref

    # Default fallback queries: curated high-yield tags with guaranteed stock hits
    defaults = [
        ("skyscraper", "cinematic aerial shot of illuminated financial district skyscrapers at night", "video"),
        ("boardroom", "cinematic photo of empty luxury glass boardroom table at night, city lights", "image"),
        ("stock market", "cinematic wide shot of stock market trading floor with glowing data monitors", "video"),
        ("city night", "dramatic shot of modern corporate skyscraper tower reflecting city lights", "image"),
        ("trading", "close up of financial charts and numerical data flowing on multiple monitors", "video"),
        ("businessman", "shadowy corporate executive standing in dark high rise office looking at city", "image"),
    ]
    query, prompt, pref = defaults[index % len(defaults)]
    return query, prompt, pref


# -----------------------------------------------------------------------------
# Dynamic Visual Beat Planner
# -----------------------------------------------------------------------------
def plan_visual_beats(
    spoken_text: str,
    total_duration: float,
    hook_duration: float = 3.5,
    min_beat_duration: float = 2.5,
    max_beat_duration: float = 3.8,
) -> List[VisualBeat]:
    """
    Partitions continuous speech into dynamic, high-retention 2.5-3.8s visual beats
    so the viewer sees a fresh, contextually matched visual every 3 seconds.
    """
    # Split text into sentences or major clauses
    sentences = re.split(r"(?<=[\.\?!])\s+", spoken_text.strip())
    if not sentences:
        sentences = [spoken_text]

    # Calculate optimal beat count (target ~3.2s per visual cut for high retention)
    total_beats = max(3, int(round(total_duration / 3.2)))
    ideal_beat_dur = total_duration / float(total_beats)

    beats: List[VisualBeat] = []
    curr_time = 0.0

    for i in range(total_beats):
        b_start = curr_time
        b_end = total_duration if i == total_beats - 1 else min(total_duration, curr_time + ideal_beat_dur)
        curr_time = b_end

        # Associate matching text snippet
        sent_idx = min(len(sentences) - 1, int((b_start / max(0.1, total_duration)) * len(sentences)))
        snippet = sentences[sent_idx]

        query, prompt, pref = extract_contextual_visual_intent(snippet, i)

        beats.append(
            VisualBeat(
                index=i,
                start_time=round(b_start, 2),
                end_time=round(b_end, 2),
                text_snippet=snippet,
                search_query=query,
                ai_prompt=prompt,
                media_preference=pref,
            )
        )

    logger.info(f"[MEDIA DIRECTOR] Planned {len(beats)} contextual visual beats across {total_duration:.1f}s.")
    return beats


# -----------------------------------------------------------------------------
# Asset Resolution Orchestrator
# -----------------------------------------------------------------------------
def resolve_all_beat_assets(
    beats: List[VisualBeat],
    palette: Dict[str, Any],
    seed: int,
    output_dir: Path = DEFAULT_CACHE_DIR,
) -> List[VisualBeat]:
    """
    Resolves a concrete visual asset for each planned visual beat using the
    pluggable provider registry (Pixabay, Local SDXL, Pexels, Wikimedia, etc.).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_beats: List[VisualBeat] = []

    for b in beats:
        asset = visual_registry.resolve_visual_beat(
            search_query=b.search_query,
            ai_prompt=b.ai_prompt,
            media_preference=b.media_preference,
            palette=palette,
            seed=seed + b.index * 13,
            output_dir=output_dir,
        )
        b.asset = asset
        resolved_beats.append(b)
        logger.info(
            f"[BEAT {b.index+1}/{len(beats)}] [{b.start_time:.1f}s - {b.end_time:.1f}s] "
            f"Provider={asset.source_provider} ({asset.media_type}) -> {asset.file_path.name}"
        )

    return resolved_beats
