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

"""UI smoke test with a stubbed Tk (no display needed): builds every page and drives the main flows."""
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))


def install_stub():
    class Widget:
        def __init__(self, *a, **k):
            self.kw = k

        def __getattr__(self, n):
            if n.startswith("__"):
                raise AttributeError(n)
            return lambda *a, **k: mock.MagicMock()

        def cget(self, k):
            return self.kw.get(k)

    class Entry(Widget):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.text = ""

        def insert(self, i, t):
            self.text = t

        def delete(self, a, b=None):
            self.text = ""

        def get(self):
            return self.text

    class Tree(Widget):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.rows, self.sel = {}, []

        def insert(self, parent, idx, iid=None, values=(), tags=()):
            self.rows[iid] = list(values)

        def get_children(self):
            return list(self.rows)

        def delete(self, *ids):
            for i in ids:
                self.rows.pop(i, None)

        def exists(self, i):
            return i in self.rows

        def item(self, i, option=None, **kw):
            if kw:
                if "values" in kw:
                    self.rows[i] = list(kw["values"])
                return None
            return self.rows[i]

        def selection(self):
            return self.sel

    class Var:
        def __init__(self, *a, value=None, **k):
            self.v = value

        def get(self):
            return self.v

        def set(self, v):
            self.v = v

    class Photo(Widget):
        def width(self):
            return 128

        def subsample(self, *a):
            return self

    tk = types.ModuleType("tkinter")
    for n in ("Frame", "Label", "Text", "PanedWindow", "Canvas", "Toplevel", "Tk"):
        setattr(tk, n, type(n, (Widget,), {}))
    tk.Entry, tk.StringVar, tk.BooleanVar, tk.PhotoImage = Entry, Var, Var, Photo
    ttk = types.ModuleType("tkinter.ttk")
    for n in ("Label", "Button", "Combobox", "Checkbutton", "Progressbar", "Scrollbar", "Separator", "Notebook", "Entry", "Style"):
        setattr(ttk, n, type(n, (Widget,), {}))
    ttk.Treeview = Tree
    ttk.Style = type("Style", (Widget,), {"theme_names": lambda s: ["clam", "vista"]})
    for m in ("filedialog", "messagebox"):
        mod = types.ModuleType("tkinter." + m)
        sys.modules["tkinter." + m] = mod
        setattr(tk, m, mod)
    tk.messagebox.showinfo = lambda *a, **k: None
    tk.ttk = ttk
    sys.modules["tkinter"], sys.modules["tkinter.ttk"] = tk, ttk


install_stub()
os.environ["APPDATA"] = tempfile.mkdtemp()
import subgrab_tk as G  # noqa: E402
import subgrab_core as C  # noqa: E402

SRT = "1\n00:00:01,000 --> 00:00:02,000\nhello\n\n2\n00:00:03,000 --> 00:00:04,000\nworld\n"


class FakeProvider:
    def __init__(self, release, name="Fake"):
        self.name, self.release = name, release

    def candidate_lists(self, info, mh=None):
        yield [{"key": "1", "release_name": self.release, "season": None, "episode": None, "hi": False, "hash": False}]

    def download(self, cand):
        return SRT.encode()


class FakeSource:
    name = "Subf2m"

    def search(self, q):
        return [{"title": "Fake Movie (2010)", "url": "http://x/y", "source": "Subf2m", "year": 2010}]

    def subs(self, item, lang):
        return [{"release": "Fake.Movie.2010.1080p", "lang": lang, "author": "me", "url": "http://x/y/1"}]

    def fetch(self, sub):
        return sub["release"], SRT.encode()


def sync_bg(app):
    def bg(fn, done):
        try:
            done(fn(), None)
        except Exception as e:
            done(None, e)
    app.bg = bg


class Smoke(unittest.TestCase):
    def setUp(self):
        G.UI.update(lang="en", rtl=False)
        self.app = G.App()
        sync_bg(self.app)
        self.tmp = tempfile.mkdtemp()

    def test_pages_exist(self):
        self.assertEqual(set(self.app.pages), {"auto", "search", "tools", "set"})
        self.app.show("search")
        self.app.show("set")
        self.app.go_back()
        self.assertEqual(self.app.current, "search")

    def test_arabic_rtl_builds(self):
        self.app.cfg["ui_lang"] = "ar"
        self.app.cfg["theme"] = "dark"
        C.save_config(self.app.cfg)
        app2 = G.App()
        self.assertTrue(G.UI["rtl"])
        self.assertEqual(G.T("Settings"), "الإعدادات")
        self.assertEqual(set(app2.pages), {"auto", "search", "tools", "set"})
        C.save_config({})

    def test_auto_page_flow(self):
        for n in ("A.2010.1080p.BluRay.x264-GRP.mkv", "B.2011.mkv"):
            open(os.path.join(self.tmp, n), "w").close()
        page = self.app.pages["auto"]
        page.set_paths([self.tmp])
        self.assertEqual(len(page.tree.rows), 2)
        self.app.make_downloader = lambda lang, log: (C.Downloader([FakeProvider("A.2010.1080p.BluRay.x264-GRP")], lang, log), [])
        with mock.patch.object(G.threading.Thread, "start", lambda self_: self_.run()):
            page.start()
        self.assertTrue(any(f.endswith(".en.srt") for f in os.listdir(self.tmp)))
        # drain queued UI updates
        while not self.app.q.empty():
            m = self.app.q.get()
            m[1](*m[2]) if m[0] == "call" else m[1](m[2], m[3])
        statuses = [r[2] for r in page.tree.rows.values()]
        self.assertTrue(any(s.startswith("OK") for s in statuses), statuses)

    def test_drop_adds_videos(self):
        open(os.path.join(self.tmp, "Z.2012.mkv"), "w").close()
        self.app.on_drop([os.path.join(self.tmp, "Z.2012.mkv")])
        self.assertEqual(self.app.current, "auto")
        self.assertEqual(len(self.app.pages["auto"].videos), 1)

    def test_search_download_preview(self):
        self.app.srcs["Subf2m"] = FakeSource()
        page = self.app.pages["search"]
        page.box.set("fake movie")
        page.src_var.set("Subf2m")
        page.run_search()
        self.assertEqual(len(page.tree.rows), 1)
        page.tree.sel = ["0"]
        with mock.patch.object(G.C, "imdb_details", return_value=None):
            page.pick_item()
        self.assertEqual(len(page.subtree.rows), 1)
        page.subtree.sel = ["0"]
        self.app.get_dest = lambda: self.tmp
        page.download()
        self.assertTrue(any(f.endswith(".srt") for f in os.listdir(self.tmp)))
        shown = []
        with mock.patch.object(G, "TextDialog", lambda app, t, text: shown.append(text)):
            page.preview()
        self.assertIn("hello", shown[0])

    def test_settings_save_and_test(self):
        page = self.app.pages["set"]
        page.order = ["Subf2m"] + [n for n in page.order if n != "Subf2m"]
        page.enabled["Subf2m"].set(True)
        page.ss_key.set("abc")
        page.lang2.set("Arabic")
        page.ui_lang.set("English")
        page.save()
        cfg = C.load_config()
        self.assertEqual(cfg["order"][0], "Subf2m")
        self.assertEqual(cfg["subsource_key"], "abc")
        self.assertEqual(cfg["language2"], "Arabic")
        self.assertIn("Subf2m", C.enabled_sources(cfg))
        with mock.patch.object(G.C, "test_source", return_value=(True, "OK - 3 results")):
            page.test("Subf2m")
        self.assertTrue(page.status["Subf2m"].startswith("\u2713"))

    def test_tools_page(self):
        p = os.path.join(self.tmp, "a.srt")
        open(p, "w").write(SRT)
        page = self.app.pages["tools"]
        page.path.set(p)
        page.shift.set("1000")
        page.apply()
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "a.fixed.srt")))

    def test_pick_dialog(self):
        v = os.path.join(self.tmp, "Movie.2010.1080p.BluRay.x264-GRP.mkv")
        open(v, "w").close()
        info = C.VideoInfo(v)
        dl = C.Downloader([FakeProvider("Movie.2010.480p.DVDRip.xvid-OTHER")], "English")
        page = self.app.pages["auto"]
        dlg = G.PickDialog(page, info, dl)
        self.assertEqual(len(dlg.items), 1)
        dlg.tree.sel = ["0"]
        dlg.use()
        self.assertTrue(any(f.endswith(".en.srt") for f in os.listdir(self.tmp)))


if __name__ == "__main__":
    unittest.main()
