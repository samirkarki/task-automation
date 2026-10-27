"""
YouTube Player Heatmap Extractor.
Extracts the official "Most Replayed" audience retention data to pinpoint
the exact timestamps where audience interest and replay spikes occurred.
"""

import json
import logging
import re
from typing import List, Optional, Tuple
import requests

from clipping.config import MIN_CLIP_DURATION, MAX_CLIP_DURATION
from clipping.models import HeatmapPoint

logger = logging.getLogger("clipping.extraction.heatmap")


def fetch_heatmap(video_url: str) -> Optional[List[HeatmapPoint]]:
    """
    Fetches the YouTube watch page and extracts heatmap points from ytInitialPlayerResponse.
    Returns list of HeatmapPoint or None if not available.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(video_url, headers=headers, timeout=20)
        resp.raise_for_status()
        text = resp.text

        # Extract ytInitialPlayerResponse JSON
        match = re.search(r"ytInitialPlayerResponse\s*=\s*({.+?})\s*;\s*(?:var\s+meta|<\/script)", text)
        if not match:
            # Alternate match pattern
            match = re.search(r"ytInitialPlayerResponse\s*=\s*({.+?})\s*;", text)
        if not match:
            logger.warning("Could not locate ytInitialPlayerResponse in video page.")
            return None

        player_data = json.loads(match.group(1))

        # Check multiMarkersPlayerBarRenderer
        overlays = player_data.get("playerOverlays", {}).get("playerOverlayRenderer", {})
        bar_renderer = (
            overlays.get("decoratedPlayerBarRenderer", {})
            .get("decoratedPlayerBarRenderer", {})
            .get("playerBar", {})
            .get("multiMarkersPlayerBarRenderer", {})
        )
        markers_map = bar_renderer.get("markersMap", [])

        heat_markers = []
        for marker_group in markers_map:
            if marker_group.get("key") == "HEATSEEKER":
                raw_markers = (
                    marker_group.get("value", {})
                    .get("heatmap", {})
                    .get("heatmapRenderer", {})
                    .get("heatMarkers", [])
                )
                for m in raw_markers:
                    rend = m.get("heatMarkerRenderer", {})
                    start_ms = rend.get("timeRangeStartMillis", 0)
                    dur_ms = rend.get("markerDurationMillis", 0)
                    intensity = float(rend.get("heatMarkerIntensityScoreNormalized", 0.0))
                    heat_markers.append(HeatmapPoint(start_ms=start_ms, duration_ms=dur_ms, intensity=intensity))

        if heat_markers:
            logger.info(f"Successfully extracted {len(heat_markers)} heatmap points from YouTube player.")
            return heat_markers

    except Exception as e:
        logger.warning(f"Error fetching heatmap for {video_url}: {e}")

    logger.info("Heatmap not available for this video (might be too new or disabled).")
    return None


def find_peak_windows(
    heatmap: Optional[List[HeatmapPoint]],
    video_duration_sec: float,
    min_duration: int = MIN_CLIP_DURATION,
    max_duration: int = MAX_CLIP_DURATION,
    top_n: int = 5,
) -> List[Tuple[float, float, float]]:
    """
    Finds the highest-intensity time windows [start_sec, end_sec, avg_intensity]
    using a sliding window over the heatmap curve.
    If no heatmap is available, falls back to evenly spaced strategic candidate windows.
    """
    target_dur = float(min(max_duration, max(min_duration, 45)))
    total_sec = int(video_duration_sec)

    if not heatmap or len(heatmap) == 0:
        logger.info("Generating strategic fallback windows based on video milestones.")
        # Common high-retention podcast intervals: 15%, 35%, 55%, 70% of video
        fallback_windows = []
        percentages = [0.15, 0.35, 0.55, 0.70, 0.85]
        for pct in percentages:
            start_s = max(60.0, float(int(total_sec * pct)))
            end_s = min(float(total_sec - 10), start_s + target_dur)
            if end_s - start_s >= min_duration:
                fallback_windows.append((start_s, end_s, 0.75))
        return fallback_windows[:top_n]

    # Convert sparse heatmap points into second-by-second intensity array
    step_duration = max(1.0, total_sec)
    intensity_curve = [0.0] * int(step_duration + 10)

    for pt in heatmap:
        start_s = max(0, int(pt.start_ms / 1000.0))
        dur_s = max(1, int(pt.duration_ms / 1000.0))
        for s in range(start_s, min(len(intensity_curve), start_s + dur_s)):
            intensity_curve[s] = max(intensity_curve[s], pt.intensity)

    # Scan with sliding window
    scored_windows = []
    window_step = 10  # Step every 10 seconds
    for start in range(60, max(61, total_sec - int(target_dur) - 30), window_step):
        end = start + int(target_dur)
        slice_vals = intensity_curve[start:end]
        avg_score = sum(slice_vals) / float(len(slice_vals)) if slice_vals else 0.0
        scored_windows.append((float(start), float(end), avg_score))

    # Sort descending by intensity
    scored_windows.sort(key=lambda x: x[2], reverse=True)

    # Deduplicate overlapping windows (keep non-overlapping top peaks)
    selected: List[Tuple[float, float, float]] = []
    for win in scored_windows:
        w_start, w_end, w_score = win
        # Check overlap with already selected
        overlap = False
        for s_start, s_end, _ in selected:
            if not (w_end < s_start or w_start > s_end):
                overlap = True
                break
        if not overlap:
            selected.append(win)
        if len(selected) >= top_n:
            break

    logger.info(f"Identified {len(selected)} peak engagement window(s) from heatmap.")
    return selected
