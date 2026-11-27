"""
SQLite Database manager for tracking clip performance metrics, A/B testing, and estimated revenue.
"""

from datetime import datetime
import logging
from pathlib import Path
import sqlite3
from typing import Dict, Any, List, Optional, Tuple

from clipping.config import DATA_DIR

logger = logging.getLogger("clipping.analytics.database")

DB_PATH = DATA_DIR / "clips.db"


class AnalyticsDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
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
                CREATE TABLE IF NOT EXISTS clips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT UNIQUE NOT NULL,
                    video_url TEXT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source_url TEXT,
                    source_channel TEXT,
                    title TEXT NOT NULL,
                    title_variant TEXT DEFAULT 'A',
                    clip_duration REAL,
                    start_sec REAL DEFAULT 0.0,
                    end_sec REAL DEFAULT 0.0,
                    heatmap_score REAL DEFAULT 0.0,
                    commentary_length INTEGER DEFAULT 0,
                    views_1h INTEGER DEFAULT 0,
                    views_24h INTEGER DEFAULT 0,
                    views_48h INTEGER DEFAULT 0,
                    views_7d INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    estimated_rpm REAL DEFAULT 0.20,
                    estimated_revenue REAL DEFAULT 0.0,
                    poll_1h_done INTEGER DEFAULT 0,
                    poll_24h_done INTEGER DEFAULT 0,
                    poll_48h_done INTEGER DEFAULT 0,
                    poll_7d_done INTEGER DEFAULT 0
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def insert_clip(
        self,
        video_id: str,
        video_url: str,
        source_url: str,
        source_channel: str,
        title: str,
        title_variant: str = "A",
        clip_duration: float = 40.0,
        start_sec: float = 0.0,
        end_sec: float = 0.0,
        heatmap_score: float = 0.0,
        commentary_length: int = 0,
        estimated_rpm: float = 0.20,
    ):
        conn = self._get_connection()
        try:
            # Auto-migrate table columns if missing
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(clips)")
            cols = [col[1] for col in cursor.fetchall()]
            if "start_sec" not in cols:
                conn.execute("ALTER TABLE clips ADD COLUMN start_sec REAL DEFAULT 0.0")
            if "end_sec" not in cols:
                conn.execute("ALTER TABLE clips ADD COLUMN end_sec REAL DEFAULT 0.0")

            conn.execute(
                """
                INSERT OR REPLACE INTO clips (
                    video_id, video_url, source_url, source_channel, title,
                    title_variant, clip_duration, start_sec, end_sec, heatmap_score,
                    commentary_length, estimated_rpm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    video_url,
                    source_url,
                    source_channel,
                    title,
                    title_variant,
                    self._safe_float(clip_duration),
                    self._safe_float(start_sec),
                    self._safe_float(end_sec),
                    self._safe_float(heatmap_score),
                    int(commentary_length or 0),
                    self._safe_float(estimated_rpm),
                ),
            )
            conn.commit()
            logger.info(f"Recorded clip in analytics database: {video_id} ('{title[:30]}...')")
        finally:
            conn.close()

    @staticmethod
    def _safe_float(val: Any) -> float:
        """Safely converts database values (bytes, str, None, numbers) to float."""
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, bytes):
            try:
                return float(val.decode("utf-8", errors="ignore"))
            except Exception:
                return 0.0
        try:
            return float(str(val))
        except Exception:
            return 0.0

    def get_clipped_intervals(self, source_url: str) -> List[Tuple[float, float]]:
        """Returns list of (start_sec, end_sec) intervals already clipped from this source URL."""
        conn = self._get_connection()
        try:
            # Check if columns exist
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(clips)")
            cols = [col[1] for col in cursor.fetchall()]
            if "start_sec" not in cols or "end_sec" not in cols:
                return []

            rows = conn.execute(
                "SELECT start_sec, end_sec FROM clips WHERE source_url = ?",
                (source_url,),
            ).fetchall()

            intervals: List[Tuple[float, float]] = []
            for r in rows:
                try:
                    s = self._safe_float(r["start_sec"])
                    e = self._safe_float(r["end_sec"])
                    if e > 0.0:
                        intervals.append((s, e))
                except Exception:
                    continue
            return intervals
        finally:
            conn.close()

    def is_interval_clipped(
        self,
        source_url: str,
        start_sec: float,
        end_sec: float,
        buffer_sec: float = 20.0,
    ) -> bool:
        """Checks if a proposed interval overlaps with an already-clipped segment."""
        intervals = self.get_clipped_intervals(source_url)
        for s, e in intervals:
            # If proposed interval overlaps within buffer_sec
            if not (end_sec < (s - buffer_sec) or start_sec > (e + buffer_sec)):
                return True
        return False

    def update_metrics(
        self,
        video_id: str,
        views: int,
        likes: int,
        comments: int,
        interval_col: Optional[str] = None,
        estimated_revenue: float = 0.0,
    ):
        conn = self._get_connection()
        try:
            if interval_col in ["views_1h", "views_24h", "views_48h", "views_7d"]:
                flag_col = f"poll_{interval_col.split('_')[1]}_done"
                conn.execute(
                    f"""
                    UPDATE clips SET
                        {interval_col} = ?,
                        likes = ?,
                        comments = ?,
                        estimated_revenue = ?,
                        {flag_col} = 1
                    WHERE video_id = ?
                    """,
                    (views, likes, comments, estimated_revenue, video_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE clips SET
                        views_24h = max(views_24h, ?),
                        likes = ?,
                        comments = ?,
                        estimated_revenue = ?
                    WHERE video_id = ?
                    """,
                    (views, likes, comments, estimated_revenue, video_id),
                )
            conn.commit()
        finally:
            conn.close()

    def get_all_clips(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            rows = conn.execute("SELECT * FROM clips ORDER BY uploaded_at DESC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_variant_comparison(self) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            rows = conn.execute("""
                SELECT
                    title_variant,
                    COUNT(*) as count,
                    AVG(views_24h) as avg_views,
                    AVG(likes) as avg_likes,
                    AVG(comments) as avg_comments
                FROM clips
                GROUP BY title_variant
            """).fetchall()
            return {r["title_variant"]: dict(r) for r in rows}
        finally:
            conn.close()

    def get_summary(self) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total_clips,
                    SUM(views_24h) as total_views,
                    SUM(likes) as total_likes,
                    SUM(comments) as total_comments,
                    SUM(estimated_revenue) as total_revenue
                FROM clips
            """).fetchone()
            if row:
                return {
                    "total_clips": row["total_clips"] or 0,
                    "total_views": row["total_views"] or 0,
                    "total_likes": row["total_likes"] or 0,
                    "total_comments": row["total_comments"] or 0,
                    "total_revenue": round(row["total_revenue"] or 0.0, 2),
                }
            return {"total_clips": 0, "total_views": 0, "total_likes": 0, "total_comments": 0, "total_revenue": 0.0}
        finally:
            conn.close()
