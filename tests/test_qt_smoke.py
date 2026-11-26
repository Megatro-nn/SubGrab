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

"""Qt UI smoke test (offscreen): builds every page and drives the main flows.
Skips cleanly when PySide6 is not installed."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    import subgrab_qt as Q
except ImportError:
    QApplication = None

import subgrab_core as C


@unittest.skipIf(QApplication is None, "PySide6 not installed")
class QtSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QApplication.instance() or QApplication([])
        cfg = C.load_config()
        Q.configure_ui(cfg)
        cls.qapp.setStyleSheet(Q.qss())
        cls.win = Q.App(cfg)

    def test_pages_build_and_show(self):
        for name in ("auto", "search", "tools", "set"):
            self.win.show_page(name)
            self.qapp.processEvents()

    def test_auto_scan_and_rename(self):
        d = tempfile.mkdtemp()
        open(os.path.join(d, "Inception.2010.1080p.BluRay.x264-GRP.mkv"), "wb").close()
        auto = self.win.pages["auto"]
        auto.set_paths([d])
        self.assertEqual(self.win.pages["auto"].tree.topLevelItemCount(), 1)
        self.assertEqual(auto.tree.topLevelItem(0).text(1), "Inception (2010)")
        tools = self.win.pages["tools"]
        tools.rn_folder.setText(d)
        plan = tools._rename_plan()
        self.assertTrue(plan[0][1].endswith("Inception (2010) 1080p bluray h264 -grp.mkv"))

    def test_settings_save(self):
        page = self.win.pages["set"]
        page.ss_key.setText("abc")
        page.save()
        self.assertEqual(C.load_config().get("subsource_key"), "abc")


if __name__ == "__main__":
    unittest.main()
