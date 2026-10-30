#!/usr/bin/env python3
"""
Ayurveda Video Performance Analytics & Feedback Loop Engine
Tracks video view velocity, retention rate, likes, comments, and subscriber conversions.
Mines metrics to dynamically refine future script hooks, pacing, and visual keywords.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
import sqlite3
from typing import Dict, Any, List, Optional

logger = logging.getLogger("ayurveda.analytics")

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "ayurveda_analytics.db"


class AyurvedaAnalyticsDB:
    """Persistent SQLite database tracking video performance & subscriber growth."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path).resolve()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS video_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT UNIQUE NOT NULL,
                    topic TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    title_variant TEXT DEFAULT 'curiosity',
                    hook_text TEXT,
                    hook_style TEXT DEFAULT 'curiosity_gap',
                    duration_sec REAL DEFAULT 0.0,
                    word_count INTEGER DEFAULT 0,
                    speech_wpm REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    views_1h INTEGER DEFAULT 0,
                    views_24h INTEGER DEFAULT 0,
                    views_48h INTEGER DEFAULT 0,
                    views_7d INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    subscribers_gained INTEGER DEFAULT 0,
                    retention_rate REAL DEFAULT 0.0,
                    avg_view_duration REAL DEFAULT 0.0,
                    youtube_url TEXT,
                    tiktok_url TEXT,
                    instagram_url TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def record_new_video(self, video_data: Dict[str, Any]) -> int:
        """Inserts a newly generated and published video record."""
        conn = self._get_connection()
        try:
            cur = conn.execute("""
                INSERT OR REPLACE INTO video_performance (
                    video_id, topic, category, title, title_variant,
                    hook_text, hook_style, duration_sec, word_count, speech_wpm,
                    youtube_url, tiktok_url, instagram_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                video_data["video_id"],
                video_data.get("topic", "Ayurveda Routine"),
                video_data.get("category", "General"),
                video_data.get("title", ""),
                video_data.get("title_variant", "curiosity"),
                video_data.get("hook_text", ""),
                video_data.get("hook_style", "curiosity_gap"),
                video_data.get("duration_sec", 0.0),
                video_data.get("word_count", 0),
                video_data.get("speech_wpm", 0.0),
                video_data.get("youtube_url", ""),
                video_data.get("tiktok_url", ""),
                video_data.get("instagram_url", ""),
            ))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def update_metrics(self, video_id: str, metrics: Dict[str, Any]):
        """Updates analytics metrics for a video after periodic scraping/API calls."""
        conn = self._get_connection()
        try:
            conn.execute("""
                UPDATE video_performance SET
                    views_24h = coalesce(?, views_24h),
                    views_48h = coalesce(?, views_48h),
                    views_7d = coalesce(?, views_7d),
                    likes = coalesce(?, likes),
                    comments = coalesce(?, comments),
                    shares = coalesce(?, shares),
                    subscribers_gained = coalesce(?, subscribers_gained),
                    retention_rate = coalesce(?, retention_rate),
                    avg_view_duration = coalesce(?, avg_view_duration)
                WHERE video_id = ?
            """, (
                metrics.get("views_24h"),
                metrics.get("views_48h"),
                metrics.get("views_7d"),
                metrics.get("likes"),
                metrics.get("comments"),
                metrics.get("shares"),
                metrics.get("subscribers_gained"),
                metrics.get("retention_rate"),
                metrics.get("avg_view_duration"),
                video_id,
            ))
            conn.commit()
        finally:
            conn.close()

    def get_all_records(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            rows = conn.execute("SELECT * FROM video_performance ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


class FeedbackOptimizer:
    """Analyzes metrics across video categories and hook styles to optimize future scripts."""

    def __init__(self, db: Optional[AyurvedaAnalyticsDB] = None):
        self.db = db or AyurvedaAnalyticsDB()

    def analyze_feedback(self) -> Dict[str, Any]:
        """
        Mines performance data and outputs feedback directives for prompt engineering.
        """
        records = self.db.get_all_records()
        if not records:
            return {
                "top_category": "digestion_agni",
                "recommended_hook_style": "curiosity_gap",
                "optimal_wpm_range": (140, 160),
                "optimal_duration_sec": 35.0,
                "prompt_directive": (
                    "Focus on daily actionable digestion and morning routines. "
                    "Use high-curiosity opening hooks that reveal an ancient biological secret."
                ),
                "insights": ["Initial baseline configuration. Awaiting audience analytics."],
            }

        # 1. Category performance (average retention and views)
        cat_stats: Dict[str, Dict[str, float]] = {}
        for r in records:
            cat = r.get("category", "General")
            if cat not in cat_stats:
                cat_stats[cat] = {"retention_sum": 0.0, "views_sum": 0, "count": 0}
            cat_stats[cat]["retention_sum"] += r.get("retention_rate", 0.0)
            cat_stats[cat]["views_sum"] += r.get("views_24h", 0)
            cat_stats[cat]["count"] += 1

        ranked_cats = sorted(
            cat_stats.keys(),
            key=lambda c: (cat_stats[c]["retention_sum"] / max(1, cat_stats[c]["count"])),
            reverse=True,
        )
        best_cat = ranked_cats[0] if ranked_cats else "digestion_agni"

        # 2. Hook style performance
        hook_stats: Dict[str, List[float]] = {}
        for r in records:
            style = r.get("hook_style", "curiosity_gap")
            retention = r.get("retention_rate", 0.0)
            hook_stats.setdefault(style, []).append(retention)

        best_hook = "curiosity_gap"
        highest_avg_retention = 0.0
        for style, rets in hook_stats.items():
            avg_ret = sum(rets) / len(rets)
            if avg_ret > highest_avg_retention:
                highest_avg_retention = avg_ret
                best_hook = style

        # 3. Construct actionable prompt directives
        directive = (
            f"AUDIENCE FEEDBACK DIRECTIVE: Prioritize the '{best_cat}' category. "
            f"The '{best_hook}' style currently achieves {highest_avg_retention:.1f}% viewer retention. "
            f"Keep voiceover delivery energetic (145-160 WPM) and opening hook under 12 words."
        )

        insights = [
            f"Top performing category: '{best_cat}'",
            f"Winning hook style: '{best_hook}' (avg retention {highest_avg_retention:.1f}%)",
            f"Total videos audited: {len(records)}",
        ]

        logger.info(f"Feedback Optimizer directives generated: {insights}")
        return {
            "top_category": best_cat,
            "recommended_hook_style": best_hook,
            "optimal_wpm_range": (145, 160),
            "optimal_duration_sec": 38.0,
            "prompt_directive": directive,
            "insights": insights,
        }
