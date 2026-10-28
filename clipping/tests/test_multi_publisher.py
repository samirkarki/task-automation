import unittest
from pathlib import Path
import tempfile

from clipping.publishing.instagram_uploader import format_instagram_caption, upload_reel_to_instagram
from clipping.publishing.tiktok_uploader import format_tiktok_title, upload_video_to_tiktok
from clipping.publishing.multi_publisher import publish_to_all_platforms


class TestMultiPublisher(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "title_a": "Why Systems Beat Motivation In Business #Shorts",
            "title_b": "How To Automate Your Operations #Shorts",
            "description": "Educational business analysis and tools.",
            "tags": ["business", "mindset", "wealth", "automation"],
        }

    def test_format_instagram_caption(self):
        caption = format_instagram_caption(self.metadata)
        self.assertIn("Why Systems Beat Motivation In Business", caption)
        self.assertNotIn("#Shorts", caption)
        self.assertIn("#reels", caption)
        self.assertIn("#business", caption)

    def test_format_tiktok_title(self):
        title = format_tiktok_title(self.metadata)
        self.assertIn("Why Systems Beat Motivation In Business", title)
        self.assertNotIn("#Shorts", title)
        self.assertIn("#fyp", title)

    def test_instagram_dry_run(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy video bytes")
            temp_path = Path(f.name)

        try:
            url = upload_reel_to_instagram(temp_path, self.metadata, dry_run=True)
            self.assertIsNotNone(url)
            self.assertIn("instagram.com/reel/DRY_RUN", url)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_tiktok_dry_run(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy video bytes")
            temp_path = Path(f.name)

        try:
            url = upload_video_to_tiktok(temp_path, self.metadata, dry_run=True)
            self.assertIsNotNone(url)
            self.assertIn("tiktok.com/@user/video/DRY_RUN", url)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_publish_to_all_platforms_dry_run(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"dummy video bytes")
            temp_path = Path(f.name)

        try:
            results = publish_to_all_platforms(
                video_path=temp_path,
                metadata=self.metadata,
                ab_variant="A",
                privacy="unlisted",
                dry_run=True,
            )
            self.assertIn("youtube", results)
            self.assertIn("instagram", results)
            self.assertIn("tiktok", results)
            self.assertTrue(results["youtube"].startswith("https://youtube.com"))
            self.assertTrue(results["instagram"].startswith("https://www.instagram.com"))
            self.assertTrue(results["tiktok"].startswith("https://www.tiktok.com"))
        finally:
            if temp_path.exists():
                temp_path.unlink()


if __name__ == "__main__":
    unittest.main()
