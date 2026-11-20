"""
Unit tests for the Multi-Profile Clipping Registry.
"""

import unittest
from clipping.profiles import get_profile, list_profiles, DEFAULT_PROFILE
from clipping.profiles.base import ClipProfile


class TestProfiles(unittest.TestCase):
    def test_list_profiles(self):
        profiles = list_profiles()
        self.assertIn("game-gta6", profiles)
        self.assertIn("game-fortnite", profiles)
        self.assertIn("mrbeast", profiles)
        self.assertIn("business", profiles)

    def test_get_gta6_profile(self):
        p = get_profile("game-gta6")
        self.assertEqual(p.name, "game-gta6")
        self.assertEqual(p.layout_mode, "smart_split_screen")
        self.assertEqual(p.facecam_position, "top")
        self.assertEqual(p.category_id, "20")
        self.assertTrue(p.duck_background_music)
        self.assertTrue(p.punch_in_on_loudness)

    def test_get_mrbeast_profile(self):
        p = get_profile("mrbeast")
        self.assertEqual(p.name, "mrbeast")
        self.assertEqual(p.layout_mode, "action_crop")
        self.assertEqual(p.category_id, "24")
        self.assertFalse(p.duck_background_music)

    def test_profile_aliases(self):
        p1 = get_profile("gta6")
        self.assertEqual(p1.name, "game-gta6")
        p2 = get_profile("fortnite")
        self.assertEqual(p2.name, "game-fortnite")

    def test_default_fallback(self):
        p = get_profile("non_existent_profile_xyz")
        self.assertEqual(p.name, DEFAULT_PROFILE.name)


if __name__ == "__main__":
    unittest.main()
