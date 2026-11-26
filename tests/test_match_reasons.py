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

"""Human-readable match reasons ("why this match") and rate-limit retry handling."""
import os
import sys
import unittest
import urllib.error
from unittest import mock

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))

import subgrab_core as C


class MatchReasons(unittest.TestCase):
    def info(self, name):
        return C.VideoInfo("/Movies/x/" + name)

    def test_hash_match(self):
        cand = {"hash": True, "quality": 2.0}
        self.assertIn("file hash", C.match_reason(cand, self.info("Inception.2010.1080p.BluRay.x264-GRP.mkv")))

    def test_good_match_same_attrs(self):
        cand = {"release_name": "Inception.2010.1080p.BluRay.x264-GRP", "quality": 2.0, "episode": None, "season": None}
        r = C.match_reason(cand, self.info("Inception.2010.1080p.BluRay.x264-GRP.mkv"))
        self.assertIn("good match", r)
        self.assertIn("release group", r)
        self.assertIn("resolution", r)

    def test_different_attrs_called_out(self):
        cand = {"release_name": "Inception.2010.720p.WEBRip.x264-OTHER", "quality": C.WEAK, "episode": None, "season": None}
        r = C.match_reason(cand, self.info("Inception.2010.1080p.BluRay.x264-GRP.mkv"))
        self.assertIn("different", r)

    def test_weak_match(self):
        cand = {"release_name": "Inception.2010.CAM.x264-GRP", "quality": 0.0, "episode": None, "season": None}
        r = C.match_reason(cand, self.info("Inception.2010.1080p.BluRay.x264-GRP.mkv"))
        self.assertIn("weak match", r)

    def test_exact_episode_noted(self):
        cand = {"release_name": "Show.S01E02.1080p.WEB.x264-GRP", "quality": 2.0, "episode": 2, "season": 1}
        r = C.match_reason(cand, self.info("Show.S01E02.1080p.WEB.x264-GRP.mkv"))
        self.assertIn("exact episode", r)

    def test_prepare_attaches_reason(self):
        dl = object.__new__(C.Downloader)  # skip __init__ side effects
        info = self.info("Inception.2010.1080p.BluRay.x264-GRP.mkv")
        subs = [{"release_name": "Inception.2010.1080p.BluRay.x264-GRP", "hash": False, "hi": False,
                 "episode": None, "season": None, "key": "1"}]
        dl._prepare(subs, info)
        self.assertIn("good match", subs[0]["reason"])


class FakeResp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return b"ok"


class RateLimitRetry(unittest.TestCase):
    def _http_error(self, code, retry_after=None):
        return urllib.error.HTTPError("http://x", code, "err",
                                      {"Retry-After": retry_after} if retry_after else {}, None)

    def test_retries_on_429_then_succeeds(self):
        calls = {"n": 0}

        def flaky(req, timeout=0):
            calls["n"] += 1
            if calls["n"] == 1:
                raise self._http_error(429, retry_after="0")
            return FakeResp()

        with mock.patch.object(C._opener, "open", side_effect=flaky), mock.patch("time.sleep"):
            self.assertEqual(C.http_request("http://x"), b"ok")
        self.assertEqual(calls["n"], 2)

    def test_gives_up_after_retries_exhausted(self):
        with mock.patch.object(C._opener, "open", side_effect=self._http_error(429)), mock.patch("time.sleep") as sleep:
            self.assertRaises(urllib.error.HTTPError, C.http_request, "http://x", retries=2)
        self.assertEqual(sleep.call_count, 2)

    def test_no_retry_on_404(self):
        with mock.patch.object(C._opener, "open", side_effect=self._http_error(404)), mock.patch("time.sleep") as sleep:
            self.assertRaises(urllib.error.HTTPError, C.http_request, "http://x")
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
