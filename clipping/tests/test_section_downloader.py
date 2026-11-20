"""
Unit tests for Targeted Section Downloading, Interval Tracking & PyAV Compatibility.
"""

import tempfile
import unittest
from pathlib import Path
from clipping.analytics.database import AnalyticsDB
from clipping.extraction.transcriber import _safe_av_open, load_audio_waveform
from clipping.models import ClipCandidate, WordSegment
from clipping.transformation.subtitle_styler import generate_karaoke_subtitles
from clipping.profiles import get_profile


class TestSectionDownloader(unittest.TestCase):
    def test_interval_tracking(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_clips.db"
            db = AnalyticsDB(db_path=db_path)

            source = "https://youtube.com/watch?v=test_vod_10h"
            self.assertFalse(db.is_interval_clipped(source, 100.0, 140.0))

            # Insert a clipped interval [100.0 - 140.0]
            db.insert_clip(
                video_id="clip_001",
                video_url="https://youtube.com/shorts/clip_001",
                source_url=source,
                source_channel="CarryisLive",
                title="Test Clip",
                clip_duration=40.0,
                start_sec=100.0,
                end_sec=140.0,
            )

            # Verify interval is recorded
            intervals = db.get_clipped_intervals(source)
            self.assertEqual(len(intervals), 1)
            self.assertEqual(intervals[0], (100.0, 140.0))

            # Overlapping interval should return True
            self.assertTrue(db.is_interval_clipped(source, 110.0, 130.0))
            self.assertTrue(db.is_interval_clipped(source, 95.0, 115.0))

            # Far unclipped interval should return False
            self.assertFalse(db.is_interval_clipped(source, 3000.0, 3040.0))

    def test_pre_cut_subtitles_offset(self):
        prof = get_profile("game-gta6")
        with tempfile.TemporaryDirectory() as tmpdir:
            out_ass = Path(tmpdir) / "pre_cut.ass"
            # Words with absolute timestamps in a 10-hour VOD
            words = [
                WordSegment(word="CRAZY", start=13650.0, end=13650.5),
                WordSegment(word="MISSION", start=13650.6, end=13651.2),
            ]
            # Generate subtitles with start_offset = 13650.0
            generate_karaoke_subtitles(
                words,
                out_ass,
                total_duration=5.0,
                profile=prof,
                start_offset=13650.0,
            )
            self.assertTrue(out_ass.exists())
            content = out_ass.read_text(encoding="utf-8")
            # In the ASS file, timestamps should now start near 0:00:00.00
            self.assertIn("0:00:00.00", content)
            self.assertIn("CRAZY", content)


if __name__ == "__main__":
    unittest.main()
