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

"""Unit tests for subgrab_core (no network, no Tk). Run: python -m unittest discover -s tests -v"""
import io
import json
import os
import struct
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import subgrab_core as S  # noqa: E402

SRT = "1\n00:00:01,000 --> 00:00:02,000\nhello\n\n2\n00:00:03,000 --> 00:00:04,000\nworld\n"


def mkzip(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, c in files.items():
            z.writestr(n, c)
    return b.getvalue()


def no_sleep(testcase):
    p = mock.patch.object(S.time, "sleep", lambda s: None)
    p.start()
    testcase.addCleanup(p.stop)


class Parsing(unittest.TestCase):
    def test_names(self):
        i = S.VideoInfo("/TV/Breaking Bad/Season 2/Breaking.Bad.S02E05.720p.mkv")
        self.assertEqual((i.title, i.season, i.episode), ("Breaking Bad", 2, 5))
        m = S.VideoInfo("/Movies/Inception (2010)/Inception.2010.1080p.mkv")
        self.assertEqual((m.title, m.year, m.is_episode), ("Inception", 2010, False))
        self.assertEqual(S.VideoInfo("/TV/Dark/Season 1/S01E02.mkv").title, "Dark")

    def test_season_words(self):
        self.assertEqual(S.season_of("Breaking Bad - Second Season"), 2)
        self.assertIsNone(S.season_of("Inception (2010)"))


class HashAndRelease(unittest.TestCase):
    def test_hash_matches_reference(self):
        data = os.urandom(300000)
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
        try:
            def ref(d):
                h = len(d)
                for chunk in (d[:65536], d[-65536:]):
                    h += sum(struct.unpack("<8192Q", chunk))
                return "%016x" % (h & 0xFFFFFFFFFFFFFFFF)
            self.assertEqual(S.opensubtitles_hash(f.name), ref(data))
        finally:
            os.unlink(f.name)

    def test_small_file_has_no_hash(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 100)
        self.assertIsNone(S.opensubtitles_hash(f.name))
        os.unlink(f.name)

    def test_release_scoring(self):
        stem = "Show.S01E02.1080p.WEB-DL.x264-GRP"
        good = S.release_score("Show.S01E02.1080p.WEB-DL.DD5.1.x264-GRP", stem)
        other = S.release_score("Show.S01E02.720p.HDTV.xvid-LOL", stem)
        self.assertGreater(good, 0.8)
        self.assertLess(other, S.WEAK)
        self.assertGreaterEqual(S.release_score("", stem), S.WEAK)
        self.assertGreaterEqual(S.release_score("anything", "Plain Name"), S.WEAK)


class TextHandling(unittest.TestCase):
    def test_cp1256_arabic_to_utf8(self):
        arabic = "مرحبا بك في العالم"
        raw = ("1\n00:00:01,000 --> 00:00:02,000\n" + arabic + "\n").encode("cp1256")
        out, ext = S.process_subtitle(raw, ".srt", "Arabic", {"utf8": True})
        self.assertIn(arabic, out.decode("utf-8"))

    def test_bom_option(self):
        out, _ = S.process_subtitle(SRT.encode(), ".srt", "English", {"bom": True})
        self.assertTrue(out.startswith(b"\xef\xbb\xbf"))

    def test_ass_and_vtt_to_srt(self):
        ass = ("[Script Info]\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
               "Dialogue: 0,0:00:01.50,0:00:03.00,Default,,0,0,0,,{\\i1}Hi{\\i0}\\Nthere, friend\n")
        out, ext = S.process_subtitle(ass.encode(), ".ass", "English", {})
        self.assertEqual(ext, ".srt")
        self.assertIn(b"00:00:01,500 --> 00:00:03,000", out)
        self.assertIn(b"there, friend", out)
        vtt = "WEBVTT\n\n00:01.000 --> 00:02.500\nHello <c.yellow>you</c>\n"
        out, ext = S.process_subtitle(vtt.encode(), ".vtt", "English", {})
        self.assertIn(b"00:00:01,000 --> 00:00:02,500", out)
        self.assertIn(b"Hello you", out)

    def test_keep_ass_when_not_converting(self):
        out, ext = S.process_subtitle(b"[Script Info]\n", ".ass", "English", {"to_srt": False})
        self.assertEqual(ext, ".ass")

    def test_ads_and_hi(self):
        text = ("1\n00:00:01,000 --> 00:00:02,000\nAdvertise your product or brand here\n\n"
                "2\n00:00:03,000 --> 00:00:04,000\n[door slams]\n\n"
                "3\n00:00:05,000 --> 00:00:06,000\nJOHN: Where are you?\n\n"
                "4\n00:00:07,000 --> 00:00:08,000\n- (sighs) Fine.\n- Okay.\n\n"
                "5\n00:00:09,000 --> 00:00:10,000\n\u266a la la \u266a\n\n"
                "6\n00:00:11,000 --> 00:00:12,000\nSynced and corrected by someone\n")
        out, _ = S.process_subtitle(text.encode(), ".srt", "English", {"ads": True, "hi": True})
        t = out.decode()
        for bad in ("Advertise", "door slams", "JOHN:", "la la", "corrected by"):
            self.assertNotIn(bad, t)
        self.assertIn("Where are you?", t)
        self.assertIn("Fine.", t)
        self.assertEqual(len(S.parse_srt_vtt(t)), 2)

    def test_timing_tools(self):
        cues = S.parse_srt_vtt(SRT)
        self.assertEqual(S.shift_cues(cues, 500)[0]["start"], 1500)
        self.assertEqual(S.shift_cues(cues, -5000)[0]["start"], 0)
        self.assertAlmostEqual(S.scale_fps(cues, 23.976, 25)[0]["start"], 1000 * 23.976 / 25, places=3)

    def test_transform_file(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "a.srt")
        open(p, "w").write(SRT)
        out, msg = S.transform_file(p, shift_ms=1000)
        self.assertTrue(out.endswith(".fixed.srt"))
        self.assertIn("00:00:02,000 --> 00:00:03,000", open(out).read())
        S.transform_file(p, shift_ms=1000, overwrite=True)
        self.assertTrue(os.path.exists(p + ".bak"))


class Archives(unittest.TestCase):
    def test_zip_bare_and_rar(self):
        self.assertEqual(list(S.archive_files(mkzip({"a.srt": SRT, "b.txt": "x"}))), ["a.srt"])
        self.assertEqual(list(S.archive_files(SRT.encode())), ["subtitle.srt"])
        with self.assertRaises(RuntimeError):
            S.archive_files(b"Rar!\x1a\x07\x00data")

    def test_rar_with_7z_path_calls_extractor(self):
        with mock.patch.object(S, "extract_with_7z", return_value={"x.srt": b"d"}) as m:
            self.assertEqual(S.archive_files(b"Rar!\x1a\x07\x00data", "7z.exe"), {"x.srt": b"d"})
            m.assert_called_once()

    def test_choose_file_for_episode(self):
        info = S.VideoInfo("/x/Show.S01E02.mkv")
        files = {"Show.S01E01.srt": b"1", "Show.S01E02.srt": b"2"}
        self.assertEqual(S.choose_file(files, info)[1], b"2")
        self.assertIsNone(S.choose_file({"a.srt": b"1", "b.srt": b"2"}, info))

    def test_save_blob(self):
        d = tempfile.mkdtemp()
        self.assertTrue(S.save_blob(mkzip({"x.srt": SRT}), "Release", d).startswith("Saved"))
        self.assertEqual(os.listdir(d), ["x.srt"])
        self.assertIn("7-Zip", S.save_blob(b"Rar!\x1a\x07\x00data", "Release", d))


SUBSCENE = {
    "search": '<ul><li><div class="title"><a href="/subtitles/breaking-bad-second-season">Breaking Bad - Second Season</a></div></li>'
              '<li><div class="title"><a href="/subtitles/breaking-bad-first-season">Breaking Bad - First Season</a></div></li></ul>',
    "title": '<table><tr><td><a href="/subtitles/breaking-bad-second-season/english/111"><span>English</span><span>Breaking.Bad.S02E05.720p.BluRay.x264-GRP</span></a></td></tr>'
             '<tr><td><a href="/subtitles/breaking-bad-second-season/english/112"><span>English</span><span>Breaking.Bad.S02E06.720p</span></a></td></tr>'
             '<tr><td><a href="/subtitles/breaking-bad-second-season/arabic/113"><span>Arabic</span><span>Breaking.Bad.S02E05.720p</span></a></td></tr></table>',
    "detail": '<a id="downloadButton" href="/subtitle/download?mac=abc">Download</a>',
}


def fake_site(url, timeout=40, headers=None):
    if "searchbytitle" in url:
        return SUBSCENE["search"].encode()
    if url.endswith(("/english/111", "/english/112", "/arabic/113")):
        return SUBSCENE["detail"].encode()
    if "/subtitle/download" in url:
        return mkzip({"Breaking.Bad.S02E05.srt": SRT})
    if "breaking-bad-second-season" in url:
        return SUBSCENE["title"].encode()
    raise urllib.error.HTTPError(url, 404, "nf", {}, None)


class WebScraper(unittest.TestCase):
    def setUp(self):
        no_sleep(self)
        p = mock.patch.object(S, "http_get", fake_site)
        p.start()
        self.addCleanup(p.stop)
        self.src = S.WebSource("Subf2m", "https://subf2m.co", S.SITES["Subf2m"][1])

    def test_search_subs_fetch(self):
        res = self.src.search("Breaking Bad")
        self.assertEqual(len(res), 2)
        second = [r for r in res if "Second" in r["title"]][0]
        subs = self.src.subs(second, "English")
        self.assertEqual(len(subs), 2)
        name, data = self.src.fetch(subs[0])
        self.assertEqual(S.kind_ext(data), ".zip")

    def test_auto_folder_download(self):
        d = tempfile.mkdtemp()
        v = os.path.join(d, "Breaking.Bad.S02E05.720p.mkv")
        open(v, "w").close()
        dl = S.Downloader([S.AutoAdapter(self.src, "English")], "English")
        code, msg = dl.fetch_for(S.VideoInfo(v))
        self.assertEqual(code, "ok", msg)
        self.assertTrue(os.path.exists(os.path.join(d, "Breaking.Bad.S02E05.720p.en.srt")))
        self.assertEqual(dl.fetch_for(S.VideoInfo(v))[0], "skip")

    def test_movies_only_source_skips_episodes(self):
        src = S.WebSource("YIFY", "https://yifysubtitles.ch", ["/search?q={q}"], movies_only=True)
        self.assertEqual(list(S.AutoAdapter(src, "English").candidate_lists(S.VideoInfo("/x/Show.S01E01.mkv"))), [])


class OpenSubtitles(unittest.TestCase):
    def setUp(self):
        no_sleep(self)
        self.calls = []
        row = {"attributes": {"release": "Movie.2010.1080p.BluRay.x264-GRP", "moviehash_match": True,
                              "files": [{"file_id": 777}], "uploader": {"name": "bob"}, "feature_details": {}}}

        def fake_get(url, timeout=40, headers=None):
            self.calls.append(url)
            if "/features" in url:
                return json.dumps({"data": [{"attributes": {"title": "Inception", "year": "2010", "imdb_id": 1375666,
                                                             "feature_type": "Movie"}}]}).encode()
            if "/subtitles" in url:
                return json.dumps({"data": [row]}).encode()
            return SRT.encode()

        def fake_req(url, data=None, headers=None, method=None, timeout=40, retries=2):
            if url.endswith("/login"):
                return json.dumps({"token": "T", "base_url": "api.opensubtitles.com"}).encode()
            if url.endswith("/download"):
                assert headers["Authorization"] == "Bearer T"
                return json.dumps({"link": "https://dl.example/x.srt", "file_name": "x.srt"}).encode()
            return fake_get(url, timeout, headers)

        for name, fn in (("http_get", fake_get), ("http_request", fake_req)):
            p = mock.patch.object(S, name, fn)
            p.start()
            self.addCleanup(p.stop)
        self.src = S.OpenSubtitlesSource("key", "user", "pw")

    def test_search_and_subs(self):
        items = self.src.search("Inception")
        self.assertEqual(items[0]["id"], 1375666)
        subs = self.src.subs(items[0], "English")
        self.assertEqual(subs[0]["id"], 777)
        self.assertIn("imdb_id=1375666", self.calls[-1])

    def test_hash_candidate_wins_and_downloads(self):
        d = tempfile.mkdtemp()
        v = os.path.join(d, "Other.Name.720p.mkv")
        with open(v, "wb") as f:
            f.write(os.urandom(200000))
        info = S.VideoInfo(v)
        dl = S.Downloader([S.AutoAdapter(self.src, "English")], "English")
        code, msg = dl.fetch_for(info)
        self.assertEqual(code, "ok", msg)
        self.assertIn("hash match", msg)
        self.assertIn("moviehash=" + info.moviehash, "".join(self.calls))

    def test_missing_login_is_explained(self):
        with self.assertRaises(RuntimeError):
            S.OpenSubtitlesSource("key", "", "").login()


class FakeProvider:
    def __init__(self, release, name="Fake"):
        self.name, self.release = name, release

    def candidate_lists(self, info, mh=None):
        yield [{"key": "1", "release_name": self.release, "season": None, "episode": None, "hi": False, "hash": False}]

    def download(self, cand):
        return SRT.encode()


class WeakMatches(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.v = os.path.join(self.d, "Movie.2010.1080p.BluRay.x264-GRP.mkv")
        open(self.v, "w").close()

    def test_weak_goes_to_review_and_manual_save(self):
        dl = S.Downloader([FakeProvider("Movie.2010.480p.DVDRip.xvid-OTHER")], "English")
        info = S.VideoInfo(self.v)
        self.assertEqual(dl.fetch_for(info)[0], "review")
        self.assertFalse(any(f.endswith(".srt") for f in os.listdir(self.d)))
        items, errs = dl.list_candidates(info)
        self.assertEqual(len(items), 1)
        self.assertIn("hello", dl.preview_item(info, items[0]))
        dl.save_item(info, items[0])
        self.assertTrue(any(f.endswith(".en.srt") for f in os.listdir(self.d)))

    def test_weak_saved_when_policy_allows(self):
        dl = S.Downloader([FakeProvider("Movie.2010.480p.DVDRip.xvid-OTHER")], "English", weak_save=True)
        self.assertEqual(dl.fetch_for(S.VideoInfo(self.v))[0], "ok")

    def test_good_match_saved_and_stats(self):
        dl = S.Downloader([FakeProvider("Movie.2010.1080p.BluRay.x264-GRP")], "English")
        self.assertEqual(dl.fetch_for(S.VideoInfo(self.v))[0], "ok")
        self.assertIn("Fake", dl.stats_text())

    def test_fallback_to_second_source_and_error_reporting(self):
        class Broken(FakeProvider):
            def candidate_lists(self, info, mh=None):
                raise urllib.error.HTTPError("u", 403, "blocked", {}, None)
                yield
        dl = S.Downloader([Broken("x", "Broken"), FakeProvider("Movie.2010.1080p.BluRay.x264-GRP", "Good")], "English")
        code, msg = dl.fetch_for(S.VideoInfo(self.v))
        self.assertEqual((code, "[Good]" in msg), ("ok", True))
        self.assertIn("Broken", dl.stats_text())
        self.assertEqual(S.Downloader([Broken("x", "Broken")], "English").fetch_for(S.VideoInfo(self.v), overwrite=True)[0], "error")

    def test_two_languages(self):
        info = S.VideoInfo(self.v)
        for lang in ("English", "Arabic"):
            S.Downloader([FakeProvider("Movie.2010.1080p.BluRay.x264-GRP")], lang).fetch_for(info)
        base = os.path.basename(self.v)[:-4]
        self.assertEqual(sorted(f for f in os.listdir(self.d) if f.endswith(".srt")), [base + ".ar.srt", base + ".en.srt"])


class SubSourceApi(unittest.TestCase):
    def test_flow(self):
        no_sleep(self)
        pack = mkzip({"Show.S01E01.srt": SRT, "Show.S01E02.srt": SRT.replace("hello", "TWO")})

        def fake(url, timeout=40, headers=None):
            if "movies/search" in url:
                return json.dumps({"data": [{"movieId": 11, "title": "Show", "type": "series", "season": 1}]}).encode()
            if url.endswith("/download"):
                return pack
            if "subtitles?" in url and "movieId=11" in url:
                return json.dumps({"data": [{"subtitleId": 901, "releaseInfo": ["Show.S01E02.720p"]}]}).encode()
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        with mock.patch.object(S, "http_get", fake):
            d = tempfile.mkdtemp()
            v = os.path.join(d, "Show.S01E02.720p.mkv")
            open(v, "w").close()
            dl = S.Downloader([S.AutoAdapter(S.SubSourceSource("k"), "English")], "English")
            self.assertEqual(dl.fetch_for(S.VideoInfo(v))[0], "ok")
            self.assertIn("TWO", open(os.path.join(d, "Show.S01E02.720p.en.srt")).read())

    def test_unconfigured_source_test(self):
        self.assertFalse(S.test_source(S.SubSourceSource(""))[0])


class SettingsHelpers(unittest.TestCase):
    def test_source_order_and_enabled(self):
        self.assertEqual(S.enabled_sources({}), S.DEFAULT_ENABLED)
        cfg = {"order": ["Subf2m", "SubSource"], "enabled": {"Subf2m": True, "SubSource": True, "OpenSubtitles": False}}
        self.assertEqual(S.enabled_sources(cfg), ["Subf2m", "SubSource"])
        self.assertEqual(set(S.build_sources({})), set(S.SOURCE_ORDER))

    def test_update_check(self):
        with mock.patch.object(S, "GITHUB_REPO", "me/SubGrab"), \
                mock.patch.object(S, "get_json", return_value={"tag_name": "v9.0.0", "html_url": "u"}):
            self.assertEqual(S.check_update(), ("9.0.0", "u"))
        with mock.patch.object(S, "GITHUB_REPO", "me/SubGrab"), \
                mock.patch.object(S, "get_json", return_value={"tag_name": "v0.0.1"}):
            self.assertIsNone(S.check_update())

    def test_videos_from_paths(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "a.mkv"), "w").close()
        open(os.path.join(d, "b.txt"), "w").close()
        self.assertEqual(len(S.videos_from_paths([d, os.path.join(d, "a.mkv")])), 1)

    def test_portable_mode(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "portable.txt"), "w").close()
        with mock.patch.object(S, "app_dir", return_value=d):
            self.assertTrue(S.is_portable())
            self.assertEqual(S.data_dir(), os.path.join(d, "data"))


if __name__ == "__main__":
    unittest.main()


class SourceDefaults(unittest.TestCase):
    def test_official_first_and_scrapers_opt_in(self):
        defaults = S.enabled_sources({})
        self.assertEqual(defaults[:2], ["OpenSubtitles", "SubSource"])
        for name in ("Subf2m",):
            self.assertNotIn(name, defaults)
            self.assertIn(name, S.SCRAPER_SOURCES)
        for name in S.OFFICIAL_SOURCES:
            self.assertIn(name, defaults)

    def test_scrapers_still_available_when_enabled(self):
        cfg = {"enabled": {"Subf2m": True, "OpenSubtitles": True, "SubSource": True}}
        self.assertEqual(S.enabled_sources(cfg), ["OpenSubtitles", "SubSource", "Subf2m"])
