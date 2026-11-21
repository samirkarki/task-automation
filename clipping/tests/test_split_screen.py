"""
Unit tests for Split-Screen / Floating PiP Framing, Multi-Corner Facecam Detection & Subtitle Styling.
"""

import tempfile
import unittest
from pathlib import Path

from clipping.transformation.facecam_detector import FacecamDetector
from clipping.transformation.video_processor import (
    build_floating_pip_filter_graph,
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
    def test_facecam_detector_no_file(self):
        """Verifies zero empty-box guarantee when no video or frame can be loaded."""
        detector = FacecamDetector()
        res = detector.detect_facecam_crop("non_existent_file.mp4")
        self.assertFalse(res["has_facecam"])
        self.assertEqual(res["confidence"], 0.0)
        self.assertEqual(res["quadrant"], "none")

    def test_facecam_detector_real_samples(self):
        """Verifies multi-corner consensus detection on real streamer footage (CarryMinati top-right)."""
        detector = FacecamDetector()
        sample_path = Path("C:/Users/Samir/.gemini/antigravity/brain/ec7ae901-da51-43f9-b0bc-1dc30a5934da/scratch/source_samples/source_13652.jpg")
        if sample_path.exists():
            res = detector.detect_facecam_crop(sample_path)
            self.assertTrue(res["has_facecam"])
            self.assertEqual(res["quadrant"], "top_right")
            self.assertGreater(res["confidence"], 0.5)

    def test_floating_pip_filter_with_facecam(self):
        """Verifies Floating Corner PiP filter graph when streamer webcam is detected."""
        facecam_coords = {
            "has_facecam": True,
            "x": 1280,
            "y": 0,
            "w": 480,
            "h": 360,
            "quadrant": "top_right",
            "confidence": 0.85,
        }
        graph = build_floating_pip_filter_graph(
            facecam_coords=facecam_coords,
            escaped_sub="subs.ass",
            clean_hook="GTA 6 EPIC MOMENT",
            border_color="0x00FFFF",
        )
        # Background blur & gameplay
        self.assertIn("split=3[bg_src][game_src][cam_src]", graph)
        self.assertIn("boxblur=25:5", graph)
        self.assertIn("overlay=0:360[base]", graph)
        # Floating badge in bottom-left corner with neon border
        self.assertIn("crop=480:360:1280:0", graph)
        self.assertIn("scale=340:255", graph)
        self.assertIn("drawbox=x=0:y=0:w=340:h=255:color=0x00FFFF@0.95:t=3", graph)
        self.assertIn("overlay=50:1420[comp]", graph)
        # Subtitles and hook banner
        self.assertIn("subtitles='subs.ass'", graph)
        self.assertIn("drawtext=text='GTA 6 EPIC MOMENT'", graph)

    def test_floating_pip_filter_zero_empty_box_fallback(self):
        """Verifies that when no webcam is detected, the floating badge is omitted completely."""
        facecam_coords = {
            "has_facecam": False,
            "x": 0,
            "y": 0,
            "w": 0,
            "h": 0,
            "quadrant": "none",
            "confidence": 0.0,
        }
        graph = build_floating_pip_filter_graph(
            facecam_coords=facecam_coords,
            escaped_sub="subs.ass",
            clean_hook="NO WEBCAM GAMEPLAY",
        )
        # Only 2-way split: background blur + uncropped gameplay
        self.assertIn("split=2[bg_src][game_src]", graph)
        self.assertNotIn("cam_src", graph)
        self.assertNotIn("overlay=50:1420", graph)
        self.assertIn("overlay=0:360[base]", graph)
        self.assertIn("[base]subtitles='subs.ass'", graph)

    def test_legacy_split_screen_alias(self):
        """Verifies backwards compatibility wrapper build_split_screen_filter_graph."""
        facecam_coords = {"x": 1440, "y": 680, "w": 480, "h": 400}
        graph = build_split_screen_filter_graph(
            facecam_coords=facecam_coords,
            split_ratio=0.36,
            escaped_sub="subs.ass",
            clean_hook="GTA 6 EPIC MOMENT",
            divider_color="0x00FFFF",
        )
        self.assertIn("boxblur=25:5", graph)
        self.assertIn("overlay=50:1420", graph)
        self.assertIn("subtitles='subs.ass'", graph)

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
        self.assertIn(",720,1", header)      # Calibrated 720 vertical margin for floating PiP

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
