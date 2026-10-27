import unittest
from pathlib import Path
import tempfile
import json
from clipping.discovery.compliance_filter import ComplianceFilter
from clipping.models import VideoMeta


class TestComplianceFilter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        td = Path(self.temp_dir.name)
        self.proc_path = td / "processed.json"
        self.takedown_path = td / "takedowns.json"
        self.whitelist_path = td / "whitelist.json"

        # Pre-populate one processed video and one takedown channel
        with open(self.proc_path, "w") as f:
            json.dump({"PROCESSED_ID": {"processed_at": "2026-01-01"}}, f)

        with open(self.takedown_path, "w") as f:
            json.dump({"TAKEDOWN_CHAN": {"reason": "opt-out"}}, f)

        with open(self.whitelist_path, "w") as f:
            json.dump([], f)

        self.filter = ComplianceFilter(
            processed_path=self.proc_path,
            takedown_path=self.takedown_path,
            whitelist_path=self.whitelist_path,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_safe_video_passes(self):
        v = VideoMeta(
            url="https://youtube.com/watch?v=GOOD123",
            video_id="GOOD123",
            title="Building a Business from Scratch",
            channel="Safe Founder",
            channel_id="SAFE_CHAN",
            view_count=100000,
            duration=900.0,
            category_id="22",
        )
        safe, reason = self.filter.is_safe(v)
        self.assertTrue(safe)
        self.assertIn("Passed", reason)

    def test_dedup_catches_already_processed(self):
        v = VideoMeta(
            url="https://youtube.com/watch?v=PROCESSED_ID",
            video_id="PROCESSED_ID",
            title="Old Video",
            channel="Safe Founder",
            channel_id="SAFE_CHAN",
            view_count=100000,
            duration=900.0,
        )
        safe, reason = self.filter.is_safe(v)
        self.assertFalse(safe)
        self.assertIn("already processed", reason)

    def test_takedown_registry_blocks_channel(self):
        v = VideoMeta(
            url="https://youtube.com/watch?v=NEW123",
            video_id="NEW123",
            title="Great Episode",
            channel="Opt Out Channel",
            channel_id="TAKEDOWN_CHAN",
            view_count=100000,
            duration=900.0,
        )
        safe, reason = self.filter.is_safe(v)
        self.assertFalse(safe)
        self.assertIn("takedown registry", reason)

    def test_blacklist_pattern_blocks_music_or_movies(self):
        v = VideoMeta(
            url="https://youtube.com/watch?v=MUSIC123",
            video_id="MUSIC123",
            title="Artist - Song Title (Official Music Video)",
            channel="Music Vevo",
            channel_id="VEVO_CHAN",
            view_count=1000000,
            duration=900.0,
        )
        safe, reason = self.filter.is_safe(v)
        self.assertFalse(safe)
        self.assertIn("blacklist", reason)

    def test_short_duration_rejected(self):
        v = VideoMeta(
            url="https://youtube.com/watch?v=TINY123",
            video_id="TINY123",
            title="Quick Tip",
            channel="Coach",
            channel_id="COACH_CHAN",
            view_count=100000,
            duration=120.0,  # 2 min < 600s
        )
        safe, reason = self.filter.is_safe(v)
        self.assertFalse(safe)
        self.assertIn("too short", reason)


if __name__ == "__main__":
    unittest.main()
