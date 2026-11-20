"""
Unit tests for Split-Screen Framing, Facecam Detection & Subtitle Styling.
"""

import tempfile
import unittest
from pathlib import Path

from clipping.transformation.facecam_detector import FacecamDetector
from clipping.transformation.video_processor import (
    build_split_screen_filter_graph,
    build_action_crop_filter_graph,
)
from clipping.transformation.subtitle_styler import (
    generate_karaoke_subtitles,
    build_ass_header,
)
from clipping.profiles import get_profile
from clipping.models import WordSegment


class TestSplitScreen(unittest.TestCase):
    def test_facecam_detector_preset(self):
        detector = FacecamDetector()
        res = detector.detect_facecam_crop("non_existent_file.mp4")
        self.assertIn("x", res)
        self.assertIn("y", res)
        self.assertIn("w", res)
        self.assertIn("h", res)
        self.assertGreater(res["confidence"], 0.5)

    def test_split_screen_filter_syntax(self):
        facecam_coords = {"x": 1440, "y": 680, "w": 480, "h": 400}
        graph = build_split_screen_filter_graph(
            facecam_coords=facecam_coords,
            split_ratio=0.36,
            escaped_sub="subs.ass",
            clean_hook="GTA 6 EPIC MOMENT",
            divider_color="0x00FFFF",
        )
        self.assertIn("vstack", graph)
        self.assertIn("drawbox", graph)
        self.assertIn("subtitles=", graph)
        self.assertIn("drawtext=", graph)
        self.assertIn("crop=480:400:1440:680", graph)

    def test_action_crop_filter_syntax(self):
        vf = build_action_crop_filter_graph(
            escaped_sub="subs.ass",
            clean_hook="MRBEAST CHALLENGE",
        )
        self.assertIn("crop=ih*(9/16):ih", vf)
        self.assertIn("scale=1080:1920", vf)
        self.assertIn("subtitles=", vf)

    def test_profile_subtitles_generation(self):
        prof = get_profile("game-gta6")
        header = build_ass_header(prof)
        self.assertIn("Montserrat ExtraBold", header)
        self.assertIn("&H0000FFFF", header)  # Yellow highlight

        with tempfile.TemporaryDirectory() as tmpdir:
            out_ass = Path(tmpdir) / "test.ass"
            words = [
                WordSegment(word="LOOK", start=0.5, end=0.9),
                WordSegment(word="AT", start=1.0, end=1.2),
                WordSegment(word="THAT", start=1.3, end=1.8),
            ]
            generate_karaoke_subtitles(words, out_ass, total_duration=2.0, profile=prof)
            self.assertTrue(out_ass.exists())
            content = out_ass.read_text(encoding="utf-8")
            self.assertIn("LOOK", content)
            self.assertIn("THAT", content)
            self.assertIn("\\fscx112\\fscy112", content)


if __name__ == "__main__":
    unittest.main()
