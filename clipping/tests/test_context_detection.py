"""
Unit tests for Multi-Signal Contextual Detection & Boundary Expansion.
"""

import tempfile
import unittest
from pathlib import Path
import numpy as np
import soundfile as sf

from clipping.extraction.comment_miner import parse_timestamp_str, score_comment_text
from clipping.extraction.audio_peak_detector import (
    analyze_audio_energy,
    find_clean_silence_boundary,
)
from clipping.extraction.clip_selector import (
    fuse_moment_seeds,
    expand_clip_boundaries_contextually,
)
from clipping.models import WordSegment


class TestContextDetection(unittest.TestCase):
    def test_comment_timestamp_parsing(self):
        self.assertEqual(parse_timestamp_str("01:23"), 83)
        self.assertEqual(parse_timestamp_str("12:00"), 720)
        self.assertEqual(parse_timestamp_str("01:10:05"), 4205)
        self.assertIsNone(parse_timestamp_str("invalid"))

    def test_comment_scoring(self):
        score, triggers = score_comment_text("Bro his face at that moment was insane 💀 lmao", likes=50)
        self.assertGreater(score, 5.0)
        self.assertIn("💀", triggers)
        self.assertIn("lmao", triggers)

    def test_audio_energy_and_silence_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test_synth.wav"
            sr = 16000
            # 6 seconds: 2s silence, 2s loud tone (scream), 2s silence
            t = np.linspace(0, 2.0, int(2.0 * sr), endpoint=False)
            silence_part = np.zeros(int(2.0 * sr), dtype=np.float32)
            loud_part = (0.8 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

            data = np.concatenate([silence_part, loud_part, silence_part])
            sf.write(str(wav_path), data, sr)

            res = analyze_audio_energy(wav_path)
            self.assertGreater(len(res["peaks"]), 0)
            self.assertGreater(len(res["silences"]), 0)

            # Test silence boundary finder
            cut_before = find_clean_silence_boundary(2.1, res["silences"], direction="before")
            self.assertLess(cut_before, 2.1)
            cut_after = find_clean_silence_boundary(3.9, res["silences"], direction="after")
            self.assertGreaterEqual(cut_after, 4.0)

    def test_fuse_moment_seeds(self):
        heatmap = [(100.0, 130.0, 0.85)]
        comments = [(115.0, 8.5, "bro died here 💀")]
        audio = [(112.0, -8.0, 4.2)]

        fused = fuse_moment_seeds(heatmap, comments, audio, video_duration_sec=600.0)
        self.assertEqual(len(fused), 1)
        self.assertIn("comments", fused[0]["sources"])
        self.assertIn("heatmap", fused[0]["sources"])
        self.assertIn("audio_scream", fused[0]["sources"])
        self.assertAlmostEqual(fused[0]["timestamp"], 115.0, delta=12.0)

    def test_contextual_boundary_expansion(self):
        words = [
            WordSegment(word="Why", start=95.0, end=95.4),
            WordSegment(word="did", start=95.5, end=95.8),
            WordSegment(word="he", start=95.9, end=96.1),
            WordSegment(word="jump?", start=96.2, end=96.6),
            WordSegment(word="He", start=97.0, end=97.3),
            WordSegment(word="got", start=97.4, end=97.6),
            WordSegment(word="wasted!", start=97.7, end=98.2),
        ]
        silences = [(93.0, 94.8), (128.0, 131.0)]

        start_s, end_s = expand_clip_boundaries_contextually(
            seed_timestamp=100.0,
            word_segments=words,
            silences=silences,
            video_duration=300.0,
            min_duration=20.0,
            max_duration=50.0,
            optimal_duration=35.0,
        )

        # Start should snap to or before 95.0
        self.assertLessEqual(start_s, 95.0)
        # Duration should be within bounds
        dur = end_s - start_s
        self.assertGreaterEqual(dur, 20.0)
        self.assertLessEqual(dur, 50.0)


if __name__ == "__main__":
    unittest.main()
