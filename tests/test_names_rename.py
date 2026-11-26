# SubGrab - downloads and fixes subtitles for your videos
# Copyright (C) 2026 Megatro-nn
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Extended filename parsing (multi-episode, anime, editions), fuzzy titles, rename with undo."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))

import subgrab_core as C


class ExtendedParsing(unittest.TestCase):
    def test_multi_episode(self):
        for name in ("Show.S01E01E02.1080p.WEB-DL.x264-GRP.mkv", "Show.S01E01-E02.mkv", "Show.S01E01-02.mkv"):
            i = C.VideoInfo("/TV/Show/" + name)
            self.assertEqual((i.title, i.season, i.episode, i.episode_end), ("Show", 1, 1, 2), name)

    def test_single_episode_has_no_range(self):
        i = C.VideoInfo("/TV/Show/Show.S01E02.1080p.WEB.x264-GRP.mkv")
        self.assertIsNone(i.episode_end)

    def test_anime_absolute_numbering(self):
        i = C.VideoInfo("/Anime/[SubsPlease] Frieren - 28 (1080p) [ABCD1234].mkv")
        self.assertEqual((i.title, i.episode, i.season, i.absolute), ("Frieren", 28, 1, True))
        i = C.VideoInfo("/Anime/One Piece - 1089 [1080p].mkv")
        self.assertEqual((i.title, i.episode), ("One Piece", 1089))
        i = C.VideoInfo("/Anime/Frieren - 03v2 [1080p].mkv")
        self.assertEqual(i.episode, 3)

    def test_anime_pattern_does_not_eat_movies(self):
        m = C.VideoInfo("/Movies/Inception (2010)/Inception.2010.1080p.BluRay.x264-GRP.mkv")
        self.assertFalse(m.absolute)
        self.assertEqual((m.title, m.year), ("Inception", 2010))
        m = C.VideoInfo("/Movies/U571 - 2000.mkv")  # trailing number equals the year: not an episode
        self.assertFalse(m.is_episode)
        self.assertEqual(m.year, 2000)

    def test_editions(self):
        m = C.VideoInfo("/Movies/Blade.Runner.1982.Final.Cut.1080p.BluRay.x264-GRP.mkv")
        self.assertEqual((m.title, m.year, m.edition), ("Blade Runner", 1982, "Final Cut"))
        m = C.VideoInfo("/Movies/Aliens.1986.Directors.Cut.1080p-GRP.mkv")
        self.assertEqual(m.edition, "Director's Cut")
        m = C.VideoInfo("/Movies/Inception.2010.1080p-GRP.mkv")
        self.assertIsNone(m.edition)

    def test_episode_ranges_overlap(self):
        info = C.VideoInfo("/TV/Show/Show.S01E02.mkv")
        self.assertTrue(C.episode_in_text("Show.S01E01E03.1080p-GRP", info))
        self.assertFalse(C.episode_in_text("Show.S01E04E05.1080p-GRP", info))
        info = C.VideoInfo("/TV/Show/Show.S01E01E02.mkv")
        self.assertTrue(C.episode_in_text("Show.S01E02.1080p-GRP", info))

    def test_fuzzy_titles(self):
        self.assertGreaterEqual(C.title_score("The Shawshank Redemption", "Shawshank Redemption"), 0.6)
        self.assertGreaterEqual(C.title_score("Breaking Bad", "Breaking Bsd"), 0.6)  # typo
        self.assertLess(C.title_score("Breaking Bad", "Better Call Saul"), 0.6)

    def test_label_shows_range(self):
        i = C.VideoInfo("/TV/Show/Show.S01E01E02.mkv")
        self.assertIn("S01E01E02", i.label())


class RenameFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._old_log = C.rename_log_path
        C.rename_log_path = lambda: os.path.join(self.tmp, "rename_history.json")

    def tearDown(self):
        C.rename_log_path = self._old_log

    def _video(self, name):
        p = os.path.join(self.tmp, name)
        open(p, "wb").close()
        return p

    def test_canonical_names(self):
        i = C.VideoInfo("/x/Breaking.Bad.S02E05.720p.BluRay.x264-GRP.mkv")
        self.assertEqual(C.canonical_name(i), "Breaking Bad - S02E05 720p bluray h264 -grp")
        m = C.VideoInfo("/x/Inception.2010.1080p.BluRay.x264-GRP.mkv")
        self.assertEqual(C.canonical_name(m), "Inception (2010) 1080p bluray h264 -grp")
        a = C.VideoInfo("/x/[SubsPlease] Frieren - 28 (1080p).mkv")
        self.assertEqual(C.canonical_name(a), "Frieren - 28 1080p -subsplease")

    def test_plan_skips_clean_names(self):
        self._video("Inception (2010).mkv")
        self.assertEqual(C.plan_renames([self.tmp]), [])

    def test_plan_skips_colliding_targets(self):
        self._video("Inception (2010).mkv")
        self._video("Inception.2010.mkv")  # its clean name is already taken
        self.assertEqual(C.plan_renames([self.tmp]), [])

    def test_plan_apply_undo_roundtrip_with_sidecar_sub(self):
        v = self._video("Inception.2010.1080p.BluRay.x264-GRP.mkv")
        s = os.path.splitext(v)[0] + ".en.srt"
        open(s, "w").write("1\n00:00:01,000 --> 00:00:02,000\nhi\n")
        plan = C.plan_renames([self.tmp])
        self.assertEqual(len(plan), 2)  # video + sidecar subtitle
        done = C.apply_renames(plan)
        self.assertEqual(len(done), 2)
        new_v = os.path.join(self.tmp, "Inception (2010) 1080p bluray h264 -grp.mkv")
        new_s = os.path.join(self.tmp, "Inception (2010) 1080p bluray h264 -grp.en.srt")
        self.assertTrue(os.path.exists(new_v) and os.path.exists(new_s))
        self.assertFalse(os.path.exists(v))
        restored = C.undo_last_rename()
        self.assertEqual(len(restored), 2)
        self.assertTrue(os.path.exists(v) and os.path.exists(s))
        self.assertFalse(os.path.exists(new_v))

    def test_undo_with_empty_history(self):
        self.assertEqual(C.undo_last_rename(), [])


if __name__ == "__main__":
    unittest.main()
