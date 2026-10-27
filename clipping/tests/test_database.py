import unittest
from pathlib import Path
import tempfile
from clipping.analytics.database import AnalyticsDB
from clipping.analytics.revenue_estimator import estimate_revenue


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        db_path = Path(self.td.name) / "test_clips.db"
        self.db = AnalyticsDB(db_path=db_path)

    def tearDown(self):
        self.td.cleanup()

    def test_insert_and_retrieve_clip(self):
        self.db.insert_clip(
            video_id="TEST_VID_1",
            video_url="https://youtube.com/shorts/TEST_VID_1",
            source_url="https://youtube.com/watch?v=SRC_1",
            source_channel="Top Podcast",
            title="Why 99% Fail In Business #Shorts",
            title_variant="A",
            clip_duration=42.0,
            heatmap_score=0.91,
            commentary_length=75,
        )
        clips = self.db.get_all_clips()
        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0]["video_id"], "TEST_VID_1")
        self.assertEqual(clips[0]["title_variant"], "A")

    def test_update_metrics_and_summary(self):
        self.db.insert_clip(
            video_id="TEST_VID_A",
            video_url="https://youtube.com/shorts/TEST_VID_A",
            source_url="https://youtube.com/watch?v=SRC_A",
            source_channel="Channel A",
            title="Title A #Shorts",
            title_variant="A",
        )
        self.db.insert_clip(
            video_id="TEST_VID_B",
            video_url="https://youtube.com/shorts/TEST_VID_B",
            source_url="https://youtube.com/watch?v=SRC_B",
            source_channel="Channel B",
            title="Title B #Shorts",
            title_variant="B",
        )

        rev_a = estimate_revenue(50000)
        self.db.update_metrics("TEST_VID_A", views=50000, likes=2500, comments=120, estimated_revenue=rev_a["total_estimated"])

        rev_b = estimate_revenue(20000)
        self.db.update_metrics("TEST_VID_B", views=20000, likes=900, comments=45, estimated_revenue=rev_b["total_estimated"])

        summary = self.db.get_summary()
        self.assertEqual(summary["total_clips"], 2)
        self.assertEqual(summary["total_views"], 70000)
        self.assertEqual(summary["total_likes"], 3400)
        self.assertGreater(summary["total_revenue"], 0.0)

        variants = self.db.get_variant_comparison()
        self.assertEqual(variants["A"]["count"], 1)
        self.assertEqual(variants["B"]["count"], 1)
        self.assertEqual(variants["A"]["avg_views"], 50000.0)
        self.assertEqual(variants["B"]["avg_views"], 20000.0)


if __name__ == "__main__":
    unittest.main()
