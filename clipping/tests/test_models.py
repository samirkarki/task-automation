import unittest
from datetime import date
from clipping.models import VideoMeta, HeatmapPoint, WordSegment, ClipCandidate


class TestModels(unittest.TestCase):
    def test_video_meta_from_ytdlp(self):
        entry = {
            "id": "dQw4w9WgXcQ",
            "title": "Build Wealth in 2026",
            "uploader": "Test Channel",
            "uploader_id": "UC12345",
            "duration": 1200,
            "view_count": 500000,
            "upload_date": "20260101",
            "license": "Creative Commons Attribution license (reuse allowed)",
        }
        meta = VideoMeta.from_ytdlp(entry)
        self.assertEqual(meta.video_id, "dQw4w9WgXcQ")
        self.assertEqual(meta.channel, "Test Channel")
        self.assertEqual(meta.duration, 1200.0)
        self.assertEqual(meta.license, "creative_commons")
        self.assertEqual(meta.upload_date, date(2026, 1, 1))

    def test_word_segment(self):
        ws = WordSegment(word="LEVERAGE", start=1.2, end=1.8)
        self.assertEqual(ws.word, "LEVERAGE")
        self.assertAlmostEqual(ws.end - ws.start, 0.6)

    def test_clip_candidate(self):
        clip = ClipCandidate(
            source_url="https://youtube.com/watch?v=123",
            source_channel="Channel",
            source_title="Title",
            start_sec=60.0,
            end_sec=105.0,
            duration=45.0,
            heatmap_score=0.92,
            hook_sentence="Shocking business reality",
        )
        self.assertEqual(clip.duration, 45.0)
        self.assertEqual(clip.heatmap_score, 0.92)


if __name__ == "__main__":
    unittest.main()
