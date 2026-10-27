"""
Data models and dataclasses for the autonomous clipping pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class VideoMeta:
    url: str
    video_id: str
    title: str
    channel: str
    channel_id: str
    view_count: int
    duration: float
    upload_date: Optional[date] = None
    category_id: Optional[str] = None
    license: Optional[str] = "standard"
    velocity: float = 0.0

    @classmethod
    def from_ytdlp(cls, entry: Dict[str, Any]) -> "VideoMeta":
        vid_id = entry.get("id", "")
        duration = float(entry.get("duration") or 0.0)
        view_count = int(entry.get("view_count") or 0)
        
        # Parse upload date if available (format YYYYMMDD)
        raw_date = entry.get("upload_date")
        parsed_date = None
        if raw_date and len(str(raw_date)) == 8:
            try:
                parsed_date = datetime.strptime(str(raw_date), "%Y%m%d").date()
            except Exception:
                parsed_date = date.today()
        else:
            parsed_date = date.today()

        return cls(
            url=f"https://www.youtube.com/watch?v={vid_id}" if not entry.get("webpage_url") else entry.get("webpage_url"),
            video_id=vid_id,
            title=entry.get("title", "Untitled"),
            channel=entry.get("uploader") or entry.get("channel") or "Unknown Channel",
            channel_id=entry.get("channel_id") or entry.get("uploader_id") or "",
            view_count=view_count,
            duration=duration,
            upload_date=parsed_date,
            category_id=str(entry.get("category_id") or "22"),
            license="creative_commons" if "Creative Commons" in str(entry.get("license", "")) else "standard",
        )


@dataclass
class HeatmapPoint:
    start_ms: int
    duration_ms: int
    intensity: float  # 0.0 to 1.0


@dataclass
class WordSegment:
    word: str
    start: float  # seconds
    end: float    # seconds


@dataclass
class ClipCandidate:
    source_url: str
    source_channel: str
    source_title: str
    start_sec: float
    end_sec: float
    duration: float
    heatmap_score: float = 0.0
    hook_sentence: str = ""
    commentary_angle: str = ""
    transcript_segment: str = ""
    word_segments: List[WordSegment] = field(default_factory=list)


@dataclass
class TransformedClip:
    clip_path: Path
    commentary_script: str
    subtitle_file: Path
    original_credit: str
    title_a: str
    title_b: str
    description: str
    tags: List[str]
    pinned_comment: str


@dataclass
class PerformanceRecord:
    video_id: str
    video_url: str
    uploaded_at: datetime
    source_url: str
    source_channel: str
    title: str
    title_variant: str
    clip_duration: float
    heatmap_score: float
    views_1h: int = 0
    views_24h: int = 0
    views_48h: int = 0
    views_7d: int = 0
    likes: int = 0
    comments: int = 0
    estimated_revenue: float = 0.0
