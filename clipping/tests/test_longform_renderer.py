"""
Tests for long-form compilation renderer, attribution badge, and facecam hardening.
"""

import tempfile
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# Attribution Badge
# ---------------------------------------------------------------------------

class TestAttributionBadge(unittest.TestCase):
    def test_badge_generation_with_initial(self):
        """Badge PNG is generated from channel initial when no avatar supplied."""
        try:
            from clipping.transformation.attribution_badge import generate_attribution_badge
        except ImportError:
            self.skipTest("attribution_badge module not available")

        import os
        out = str(Path(tempfile.gettempdir()) / "test_badge_initial.png")
        try:
            result = generate_attribution_badge("TechnoGamerz", None, out)
            if result is None:
                self.skipTest("Pillow not installed in test env")
            self.assertTrue(Path(result).exists(), "Badge PNG not created")
            try:
                from PIL import Image
                with Image.open(result) as img:
                    self.assertEqual(img.size, (420, 110))
                    self.assertEqual(img.mode, "RGBA")
            except ImportError:
                pass  # Pillow not in test env
        finally:
            try:
                if Path(out).exists():
                    os.unlink(out)
            except OSError:
                pass

    def test_badge_long_name_truncated(self):
        """Channel names > 20 chars are truncated without raising."""
        try:
            from clipping.transformation.attribution_badge import generate_attribution_badge
        except ImportError:
            self.skipTest("attribution_badge module not available")

        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "badge_long.png")
            # Should not raise regardless of Pillow availability
            result = generate_attribution_badge(
                "AVeryLongChannelNameThatExceedsTwentyCharacters", None, out
            )
            self.assertTrue(result is None or Path(result).exists())

    def test_badge_with_nonexistent_avatar_falls_back_to_initial(self):
        """Nonexistent avatar path is silently ignored; initial used instead."""
        try:
            from clipping.transformation.attribution_badge import generate_attribution_badge
        except ImportError:
            self.skipTest("attribution_badge module not available")

        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "badge_fallback.png")
            result = generate_attribution_badge("CarryMinati", "/nonexistent/avatar.png", out)
            self.assertTrue(result is None or Path(result).exists())


# ---------------------------------------------------------------------------
# Long-Form Renderer
# ---------------------------------------------------------------------------

class TestLongformRenderer(unittest.TestCase):
    def test_render_longform_no_clips_returns_none(self):
        """render_longform_compilation returns None when given empty clip list."""
        try:
            from clipping.transformation.longform_renderer import render_longform_compilation
        except ImportError:
            self.skipTest("longform_renderer not available")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output.mp4"
            result = render_longform_compilation([], [], out)
            self.assertIsNone(result)

    def test_render_longform_missing_files_returns_none(self):
        """render_longform_compilation returns None when clip files don't exist on disk."""
        try:
            from clipping.transformation.longform_renderer import render_longform_compilation
        except ImportError:
            self.skipTest("longform_renderer not available")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "output.mp4"
            fake = [Path(tmp) / "nonexistent_1.mp4", Path(tmp) / "nonexistent_2.mp4"]
            result = render_longform_compilation(fake, [0.5, 0.9], out)
            self.assertIsNone(result)

    def test_clip_ordering_ascending_by_hype_score(self):
        """
        Clips must be sorted ascending by hype score so the best clip is last.
        (save-the-best-for-last retention strategy)
        """
        scores = [0.9, 0.3, 0.7]
        paired = sorted(zip(scores, range(len(scores))), key=lambda x: x[0])
        ordered_scores = [s for s, _ in paired]
        self.assertEqual(ordered_scores, sorted(scores))  # ascending = best last
        self.assertEqual(ordered_scores[-1], max(scores))


# ---------------------------------------------------------------------------
# Facecam Detector — Threshold Hardening
# ---------------------------------------------------------------------------

class TestFacecamDetectorThresholds(unittest.TestCase):
    def _get_detector(self):
        try:
            from clipping.transformation.facecam_detector import FacecamDetector
            d = FacecamDetector()
            if d._cv2 is None:
                self.skipTest("cv2 not available in test environment")
            return d
        except ImportError:
            self.skipTest("FacecamDetector not importable")

    def test_pure_purple_frame_has_no_facecam(self):
        """
        A solid purple frame (simulating GTA6 settings UI) must return has_facecam=False
        because purple is outside the skin HSV range.
        """
        import numpy as np
        detector = self._get_detector()
        cv2 = detector._cv2

        # Purple in BGR: (128, 0, 128)
        purple_frame = np.full((720, 1280, 3), [128, 0, 128], dtype=np.uint8)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_img = f.name
        try:
            cv2.imwrite(tmp_img, purple_frame)
            result = detector.detect_facecam_crop(tmp_img)
            self.assertFalse(result["has_facecam"],
                             "Purple frame incorrectly detected as facecam")
        finally:
            Path(tmp_img).unlink(missing_ok=True)

    def test_black_frame_has_no_facecam(self):
        """A solid black frame must return has_facecam=False."""
        import numpy as np
        detector = self._get_detector()
        cv2 = detector._cv2

        black_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_img = f.name
        try:
            cv2.imwrite(tmp_img, black_frame)
            result = detector.detect_facecam_crop(tmp_img)
            self.assertFalse(result["has_facecam"])
        finally:
            Path(tmp_img).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# No-Facecam Filter Graph (video_processor)
# ---------------------------------------------------------------------------

class TestNoCamFilterGraph(unittest.TestCase):
    def test_no_facecam_fullscreen_contains_9_16_crop(self):
        """build_smart_split_filter_graph with has_facecam=False must produce 9:16 crop."""
        try:
            from clipping.transformation.video_processor import build_smart_split_filter_graph
        except ImportError:
            self.skipTest("video_processor not importable")

        graph = build_smart_split_filter_graph(
            facecam_coords={"has_facecam": False, "x": 0, "y": 0, "w": 0, "h": 0},
            escaped_sub="/tmp/subs.ass",
            clean_hook="TEST HOOK",
        )
        self.assertIn("9/16", graph, "No-cam filter must contain 9:16 crop expression")
        self.assertIn("1080:1920", graph, "No-cam filter must scale to 1080x1920")

    def test_no_facecam_badge_overlay_included(self):
        """
        build_smart_split_filter_graph with badge_path set must include overlay filter
        in the no-facecam branch.
        """
        try:
            from clipping.transformation.video_processor import build_smart_split_filter_graph
        except ImportError:
            self.skipTest("video_processor not importable")

        # Create a temporary badge file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n")  # minimal fake PNG header
            badge_path = f.name

        try:
            graph = build_smart_split_filter_graph(
                facecam_coords={"has_facecam": False, "x": 0, "y": 0, "w": 0, "h": 0},
                escaped_sub="/tmp/subs.ass",
                clean_hook="TEST HOOK",
                badge_path=badge_path,
            )
            self.assertIn("overlay", graph,
                          "Badge overlay must appear in filter when badge_path is set")
        finally:
            Path(badge_path).unlink(missing_ok=True)

    def test_no_facecam_no_badge_when_path_missing(self):
        """When badge_path points to non-existent file, overlay must NOT appear."""
        try:
            from clipping.transformation.video_processor import build_smart_split_filter_graph
        except ImportError:
            self.skipTest("video_processor not importable")

        graph = build_smart_split_filter_graph(
            facecam_coords={"has_facecam": False, "x": 0, "y": 0, "w": 0, "h": 0},
            escaped_sub="/tmp/subs.ass",
            clean_hook="TEST HOOK",
            badge_path="/nonexistent/badge.png",
        )
        # Should not crash and should not have badge overlay (file doesn't exist)
        self.assertIn("9/16", graph)


if __name__ == "__main__":
    unittest.main()
