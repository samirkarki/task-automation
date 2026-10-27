import unittest
from clipping.extraction.heatmap import find_peak_windows
from clipping.models import HeatmapPoint


class TestHeatmap(unittest.TestCase):
    def test_find_peak_windows_with_data(self):
        # Create dummy heatmap points with peak around 120s
        heatmap = [
            HeatmapPoint(start_ms=0, duration_ms=60000, intensity=0.2),
            HeatmapPoint(start_ms=60000, duration_ms=60000, intensity=0.4),
            HeatmapPoint(start_ms=120000, duration_ms=60000, intensity=0.95),  # Peak
            HeatmapPoint(start_ms=180000, duration_ms=60000, intensity=0.5),
            HeatmapPoint(start_ms=240000, duration_ms=60000, intensity=0.3),
        ]
        windows = find_peak_windows(heatmap, video_duration_sec=300.0, min_duration=30, max_duration=50, top_n=2)
        self.assertGreaterEqual(len(windows), 1)
        top_start, top_end, top_score = windows[0]
        # Should be within or near the peak interval
        self.assertGreaterEqual(top_score, 0.4)
        self.assertGreaterEqual(top_end - top_start, 30.0)

    def test_find_peak_windows_fallback(self):
        # When heatmap is None or empty, should return strategic milestone windows
        windows = find_peak_windows(None, video_duration_sec=1200.0, min_duration=30, max_duration=50, top_n=3)
        self.assertEqual(len(windows), 3)
        for start, end, score in windows:
            self.assertGreaterEqual(end - start, 30.0)
            self.assertGreaterEqual(start, 60.0)  # Skips intro filler


if __name__ == "__main__":
    unittest.main()
