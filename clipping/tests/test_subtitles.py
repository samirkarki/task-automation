import unittest
from pathlib import Path
import tempfile
from clipping.transformation.subtitle_styler import generate_karaoke_subtitles, format_ass_time
from clipping.models import WordSegment


class TestSubtitles(unittest.TestCase):
    def test_format_ass_time(self):
        self.assertEqual(format_ass_time(0.0), "0:00:00.00")
        self.assertEqual(format_ass_time(65.5), "0:01:05.50")
        self.assertEqual(format_ass_time(3661.25), "1:01:01.25")

    def test_generate_karaoke_subtitles_with_segments(self):
        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "test.ass"
            words = [
                WordSegment(word="LEVERAGE", start=0.5, end=1.0),
                WordSegment(word="IS", start=1.0, end=1.2),
                WordSegment(word="EVERYTHING", start=1.2, end=1.8),
                WordSegment(word="IN", start=1.8, end=2.0),
                WordSegment(word="BUSINESS", start=2.0, end=2.6),
            ]
            generate_karaoke_subtitles(words, out_file)
            self.assertTrue(out_file.exists())
            content = out_file.read_text(encoding="utf-8")
            self.assertIn("[Script Info]", content)
            self.assertIn("PlayResX: 1080", content)
            self.assertIn("Dialogue:", content)
            self.assertIn("&H0000FFFF&", content)  # Yellow highlight code

    def test_generate_karaoke_subtitles_text_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "fallback.ass"
            generate_karaoke_subtitles("Build systems that compound while you sleep", out_file, total_duration=30.0)
            self.assertTrue(out_file.exists())
            content = out_file.read_text(encoding="utf-8")
            self.assertIn("Dialogue:", content)
            self.assertIn("COMPOUND", content)


if __name__ == "__main__":
    unittest.main()
