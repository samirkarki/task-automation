"""
Multi-gate compliance and safety filter.
Protects the channel against copyright strikes, reuse penalties, and creator objections.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
import re
from typing import Tuple, Dict, Any, List

from clipping.config import DATA_DIR, BLACKLIST_PATTERNS
from clipping.models import VideoMeta

logger = logging.getLogger("clipping.discovery.compliance_filter")


class ComplianceFilter:
    """
    Multi-gate compliance checker. Every candidate video must pass ALL checks.
    """

    def __init__(
        self,
        processed_path: Path = DATA_DIR / "processed_videos.json",
        takedown_path: Path = DATA_DIR / "takedown_registry.json",
        whitelist_path: Path = DATA_DIR / "channel_whitelist.json",
    ):
        self.processed_path = processed_path
        self.takedown_path = takedown_path
        self.whitelist_path = whitelist_path
        self._load_registries()

    def _load_registries(self):
        self.processed: Dict[str, Any] = self._read_json(self.processed_path)
        self.takedowns: Dict[str, Any] = self._read_json(self.takedown_path)
        raw_whitelist = self._read_json(self.whitelist_path)
        if isinstance(raw_whitelist, list):
            self.whitelist = {entry.get("channel_id"): entry for entry in raw_whitelist if isinstance(entry, dict)}
        else:
            self.whitelist = raw_whitelist

    def _read_json(self, path: Path) -> Any:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read {path.name}: {e}. Initializing empty.")
        return {}

    def _save_json(self, path: Path, data: Any):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def is_safe(self, video: VideoMeta) -> Tuple[bool, str]:
        """
        Runs candidate video through all safety gates.
        Returns (True, reason) if safe, (False, reason) if unsafe.
        """
        # Gate 1: Deduplication (don't re-clip previously processed videos)
        if video.video_id in self.processed:
            return False, f"Video already processed on {self.processed[video.video_id].get('processed_at', 'earlier')}"

        # Gate 2: Creator Takedown Registry (respect creators who opted out)
        if video.channel_id in self.takedowns:
            reason = self.takedowns[video.channel_id].get("reason", "Creator requested no clipping")
            return False, f"Channel is blacklisted in takedown registry: {reason}"

        # Gate 3: Content Blacklist Patterns (Music, full movies, sports)
        title_lower = video.title.lower()
        for pattern in BLACKLIST_PATTERNS:
            if re.search(pattern, title_lower):
                return False, f"Title matched blacklist pattern: '{pattern}'"

        # Gate 4: Category Safety (10=Music, 17=Sports, 43=Shows)
        if str(video.category_id) in ["10", "17", "43"]:
            return False, f"Restricted category ID: {video.category_id}"

        # Gate 5: Duration sanity check (must be at least 10 minutes)
        if video.duration < 600:
            return False, f"Video too short for rich clipping ({video.duration:.0f}s < 600s)"

        return True, "Passed all safety and compliance gates ✓"

    def register_processed(self, video_id: str, clips_count: int, metadata: Dict[str, Any] = None):
        """Records video in processed registry to prevent re-processing."""
        self.processed[video_id] = {
            "processed_at": datetime.now().isoformat(),
            "clips_generated": clips_count,
            "metadata": metadata or {},
        }
        self._save_json(self.processed_path, self.processed)
        logger.info(f"Registered video {video_id} with {clips_count} clip(s).")

    def blacklist_channel(self, channel_id: str, reason: str = "Takedown request"):
        """Adds a channel to the permanent takedown registry."""
        self.takedowns[channel_id] = {
            "blacklisted_at": datetime.now().isoformat(),
            "reason": reason,
        }
        self._save_json(self.takedown_path, self.takedowns)
        logger.warning(f"Permanently blacklisted channel: {channel_id} ({reason})")
