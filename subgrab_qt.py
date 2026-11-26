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

"""
SubGrab - the Qt (PySide6) interface. All logic lives in subgrab_core.py.

Pages: Auto Folder, Search, Subtitle Tools, Settings.
Background work runs on threads; results reach the GUI through a queue that a
QTimer drains on the main thread (the same pattern the Tk UI uses).
"""
import os
import queue
import subprocess
import sys
import threading
import time
import webbrowser

from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher, QSize
from PySide6.QtGui import QPixmap, QIcon, QGuiApplication
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QStackedWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QTreeWidget, QTreeWidgetItem,
                               QProgressBar, QPlainTextEdit, QFileDialog, QMessageBox, QDialog, QTabWidget,
                               QSplitter, QAbstractItemView, QFrame, QGridLayout, QToolButton)

import subgrab_core as C
from subgrab_core import (APP_NAME, DEFAULT_CLEAN, GITHUB_REPO, KEY_SOURCES, LANGS, SOURCE_ORDER, VERSION,
                          VideoInfo, dlog, friendly_error)
from subgrab_i18n import UI, T
from subgrab_icons import ICONS

try:
    from subgrab_assets import LOGO_PNG_B64
except Exception:  # pragma: no cover
    LOGO_PNG_B64 = ""

# --------------------------------------------------------------------- theme
# Dark and light color themes.
LIGHT = dict(bg="#EBEBEB", panel="#FFFFFF", fg="#26282A", muted="#61666B", accent="#558EEF", accent2="#4083C9",
             hover="#DDDDDD", border="#C4C4C4", entry="#FFFFFF", head="#EBEBEB",
             select="#C5CFD5", selfg="#000000", ok="#1E8E00", warn="#B26A00", bad="#CC0202",
             grid2="#F8F8F8", toolbar="#F5F5F5", toolbar_hover="#E4E4E4", toolbar_press="#DADADA",
             toolbar_sep="#D1D1D1", rail="#D5D5D5", sep="#D1D1D1", rail_icon="#3F444A",
             tb_fg="#26282A", tb_dim="#61666B", pill="#E4E4E4", sb_prog_bg="#D0D0D0",
             poster_bg="#E8EDF5", chip_ok_bg="#D9F2E0", chip_warn_bg="#FCEBCF")
DARK = dict(bg="#2B2B2C", panel="#3C3F41", fg="#C0C0C0", muted="#9A9A9A", accent="#209FDB", accent2="#4A88C7",
            hover="#353638", border="#646464", entry="#232323", head="#2B2B2C",
            select="#555555", selfg="#FFFFFF", ok="#1FBB00", warn="#D08A2E", bad="#CC4A4A",
            grid2="#2E2E2E", toolbar="#2E2E2E", toolbar_hover="#3A3B3C", toolbar_press="#454647",
            toolbar_sep="#1F1F1F", rail="#262626", sep="#515151", rail_icon="#9A9A9A",
            tb_fg="#C0C0C0", tb_dim="#9A9A9A", pill="#3A3B3C", sb_prog_bg="#232323",
            poster_bg="#232B3A", chip_ok_bg="#1E3A26", chip_warn_bg="#4A3D10")
P = dict(LIGHT)


def system_is_dark():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except Exception:
        pal = QGuiApplication.palette()
        return pal.window().color().lightness() < 128


def configure_ui(cfg):
    UI["lang"] = cfg.get("ui_lang", "en")
    UI["rtl"] = UI["lang"] == "ar"
    theme = cfg.get("theme", "system")
    dark = theme == "dark" or (theme == "system" and system_is_dark())
    P.clear()
    P.update(DARK if dark else LIGHT)
    P["dark"] = dark


def qss():
    return f"""
    QMainWindow, QDialog {{ background: {P['bg']}; }}
    QWidget {{ color: {P['fg']}; font-family: "Segoe UI"; font-size: 13px; }}
    /* ---- top toolbar (dark in both themes) ---- */
    #toolbar {{ background: {P['toolbar']}; border-bottom: 1px solid {P['toolbar_sep']}; }}
    #tb_title {{ color: {P["tb_fg"]}; font-size: 15px; font-weight: bold; }}
    #tb_tag {{ color: {P["tb_dim"]}; font-size: 10px; }}
    QToolButton#toolbtn {{ color: {P["tb_fg"]}; background: transparent; border: none; border-radius: 7px;
        padding: 7px 12px; font-size: 12px; }}
    QToolButton#toolbtn:hover {{ background: {P['toolbar_hover']}; }}
    QToolButton#toolbtn:pressed {{ background: {P['toolbar_press']}; }}
    QToolButton#themebtn {{ color: {P["tb_fg"]}; background: {P["pill"]}; border: none; border-radius: 14px;
        font-size: 11px; padding-right: 8px; }}
    QToolButton#themebtn:hover {{ background: {P['toolbar_press']}; }}
    /* ---- left icon rail ---- */
    #rail {{ background: {P['rail']}; }}
    QToolButton#railbtn {{ background: transparent; border: none; border-radius: 9px; }}
    QToolButton#railbtn:hover {{ background: {P['hover']}; }}
    QToolButton#railbtn[active="true"] {{ background: {P['select']}; }}
    /* ---- content / status bar ---- */
    #panel {{ background: {P['bg']}; border: none; }}
    #statusbar {{ background: {P['toolbar']}; border-top: 1px solid {P['toolbar_sep']}; }}
    #sb_text {{ color: {P["tb_fg"]}; font-size: 10px; }}
    #sb_prog {{ background: {P["sb_prog_bg"]}; border: none; border-radius: 4px; }}
    #sb_prog::chunk {{ background: #8DA5B3; border-radius: 4px; }}
    #banner {{ background: {P['accent']}; color: white; font-weight: bold; padding: 6px; border: none; }}
    /* ---- inputs / buttons ---- */
    QLineEdit, QComboBox, QPlainTextEdit, QTabWidget::pane {{
        background: {P['entry']}; border: 1px solid {P['border']}; border-radius: 5px; padding: 5px; }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {P['accent']}; }}
    QComboBox QAbstractItemView {{ background: {P['entry']}; color: {P['fg']};
        selection-background-color: {P['accent']}; }}
    QPushButton {{ background: {P['head']}; border: 1px solid {P['border']}; border-radius: 5px; padding: 7px 14px; }}
    QPushButton:hover {{ background: {P['hover']}; }}
    QPushButton:disabled {{ color: {P['muted']}; }}
    QPushButton#primary {{ background: {P['accent']}; color: white; font-weight: bold; border: none; }}
    QPushButton#primary:hover {{ background: {P['accent2']}; }}
    /* ---- tables ---- */
    QTreeWidget {{ background: {P['panel']}; alternate-background-color: {P['grid2']};
        border: 1px solid {P['sep']}; }}
    QTreeWidget::item {{ padding: 6px 4px; border: none; }}
    QTreeWidget::item:selected {{ background: {P['select']}; color: {P['selfg']}; }}
    QHeaderView::section {{ background: {P['head']}; color: {P['muted']}; border: none;
        border-bottom: 1px solid {P['sep']}; padding: 6px; font-weight: bold; font-size: 11px; }}
    QProgressBar {{ background: {P['head']}; border: 1px solid {P['border']}; border-radius: 4px; text-align: center; }}
    QProgressBar::chunk {{ background: {P['accent']}; }}
    QTabBar::tab {{ background: {P['head']}; padding: 8px 16px; border: 1px solid {P['border']}; }}
    QTabBar::tab:selected {{ background: {P['panel']}; border-bottom: 2px solid {P['accent2']}; }}
    #muted {{ color: {P['muted']}; }}
    """


# ---------------------------------------------------------------- svg icons
_ICON_CACHE = {}

def icon(name, color, size=20):
    """Colored QIcon rendered from the bundled Phosphor SVGs."""
    key = (name, color, size)
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QPainter
    from PySide6.QtSvg import QSvgRenderer
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    rend = QSvgRenderer(ICONS[name].encode("utf-8"))
    p = QPainter(pm)
    rend.render(p, QRectF(0, 0, size * 2, size * 2))
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(0, 0, size * 2, size * 2, QColor(color))
    p.end()
    pm.setDevicePixelRatio(2)
    ic = QIcon(pm)
    _ICON_CACHE[key] = ic
    return ic

# ------------------------------------------------------------ thread helpers
class Page(QWidget):
    """A page plus the app's background-callback queue."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setObjectName("panel")

    def on_show(self):
        pass

    def bg(self, fn, done):
        self.app.bg(fn, done)

    def ui(self, fn, *args):
        self.app.q.put(("call", fn, args))


def tag_row(item, tag):
    from PySide6.QtGui import QColor
    colors = {"ok": P["ok"], "review": P["warn"], "bad": P["bad"]}
    if tag in colors:
        item.setForeground(item.columnCount() - 1, QColor(colors[tag]))


def make_tree(columns, headings):
    tree = QTreeWidget()
    tree.setColumnCount(len(columns))
    tree.setHeaderLabels(headings)
    tree.setRootIsDecorated(False)
    tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
    tree.setUniformRowHeights(True)
    tree.setAlternatingRowColors(True)
    return tree


def options_row(app, bom=True):
    """The subtitle-clean-up checkboxes shared by Auto Folder, Search and Tools.
    Laid out over two rows so nothing is cut off on smaller windows."""
    items = [("utf8", "Convert to UTF-8"), ("to_srt", "Convert to SRT"), ("ads", "Remove ads / watermarks"),
             ("hi", "Remove hearing-impaired tags")]
    if bom:
        items.append(("bom", "Add BOM (older TVs/players)"))
    box = QVBoxLayout()
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(2)
    top = QHBoxLayout()
    top.setContentsMargins(0, 0, 0, 0)
    top.addWidget(QLabel(T("Subtitle options:")))
    for key, text in items[:3]:
        top.addWidget(_clean_cb(app, key, text))
    top.addStretch(1)
    box.addLayout(top)
    if len(items) > 3:
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addSpacing(120)
        for key, text in items[3:]:
            bottom.addWidget(_clean_cb(app, key, text))
        bottom.addStretch(1)
        box.addLayout(bottom)
    w = QWidget()
    w.setLayout(box)
    return w


def _clean_cb(app, key, text):
    cb = QCheckBox(T(text))
    cb.setChecked(app.clean_opts_state.get(key, False))
    cb.toggled.connect(lambda on, k=key: app.set_clean(k, on))
    return cb


class TextDialog(QDialog):
    def __init__(self, parent, title, text):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 520)
        lay = QVBoxLayout(self)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        box.setStyleSheet("font-family: Consolas, monospace;")
        lay.addWidget(box)
        btn = QPushButton(T("Close"))
        btn.clicked.connect(self.accept)
        lay.addWidget(btn, alignment=Qt.AlignLeft if not UI["rtl"] else Qt.AlignRight)


class PickDialog(QDialog):
    """Manual pick: every candidate from every source, with preview."""

    def __init__(self, page, info, downloader):
        super().__init__(page)
        self.page, self.info, self.dl, self.app = page, info, downloader, page.app
        self.setWindowTitle(f"{T('Pick manually...').rstrip('.')} - {info.label()}")
        self.resize(980, 540)
        lay = QVBoxLayout(self)
        title = QLabel(os.path.basename(info.path))
        title.setStyleSheet("font-weight: bold;")
        lay.addWidget(title)
        self.tree = make_tree(("src", "rel", "score", "match", "why"),
                              (T("Source"), T("Release"), T("Score"), T("Match"), T("Why")))
        self.tree.setColumnWidth(0, 110)
        self.tree.setColumnWidth(1, 460)
        self.tree.setColumnWidth(4, 220)
        self.tree.itemDoubleClicked.connect(lambda *_: self.use())
        lay.addWidget(self.tree)
        bar = QHBoxLayout()
        for text, fn in ((T("Preview"), self.preview), (T("Use selected"), self.use), (T("Close"), self.accept)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            bar.addWidget(b)
        self.status = QLabel("Looking for candidates...")
        bar.addWidget(self.status, 1)
        lay.addLayout(bar)
        self.items = {}
        self.bg(lambda: self.dl.list_candidates(info), self.loaded)
        self.show()

    def loaded(self, res, err):
        if err:
            self.status.setText("Error: " + friendly_error(err))
            return
        items, errs = res
        for i, it in enumerate(items):
            c = it["cand"]
            row = QTreeWidgetItem([it["prov"].name, c.get("release_name", ""), f"{c['quality']:.2f}",
                                   "file hash" if c.get("hash") else ("good" if c["quality"] >= C.WEAK else "weak"),
                                   c.get("reason", "")])
            tag_row(row, "ok" if (c.get("hash") or c["quality"] >= C.WEAK) else "review")
            self.tree.addTopLevelItem(row)
            self.items[str(i)] = it
            row.setData(0, Qt.UserRole, str(i))
        msg = f"{len(items)} candidate(s)"
        if errs:
            msg += "   |   " + "; ".join(errs)
        self.status.setText(msg)

    def current(self):
        sel = self.tree.selectedItems()
        return self.items.get(sel[0].data(0, Qt.UserRole)) if sel else None

    def preview(self):
        it = self.current()
        if not it:
            return
        self.status.setText("Loading preview...")
        self.bg(lambda: self.dl.preview_item(self.info, it), self._shown)

    def _shown(self, text, err):
        if err:
            self.status.setText("Error: " + friendly_error(err))
        else:
            self.status.setText("")
            TextDialog(self, T("Preview"), text).exec()

    def use(self):
        it = self.current()
        if not it:
            return
        self.status.setText("Saving...")
        self.bg(lambda: self.dl.save_item(self.info, it), self._saved)

    def _saved(self, path, err):
        if err:
            self.status.setText("Error: " + friendly_error(err))
            return
        self.page.set_status(self.info.path, f"OK (manual)  ->  {os.path.basename(path)}", "ok")
        self.accept()


# ------------------------------------------------- details panel (auto page)
class DetailsPanel(QFrame):
    """Right-side movie details + subtitle candidates for the selected video."""

    def __init__(self, page):
        super().__init__(page)
        self.page, self.app = page, page.app
        self.setObjectName("details")
        self.setMinimumWidth(320)
        self.setMaximumWidth(440)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        hdr = QLabel(T("Movie details"))
        hdr.setStyleSheet("font-size: 16px; font-weight: bold;")
        lay.addWidget(hdr)
        self.fname = QLabel("")
        self.fname.setObjectName("muted")
        self.fname.setStyleSheet("font-size: 10px;")
        lay.addWidget(self.fname)
        row = QHBoxLayout()
        self.poster = QLabel()
        self.poster.setFixedSize(120, 178)
        self.poster.setAlignment(Qt.AlignCenter)
        self.poster.setObjectName("poster")
        row.addWidget(self.poster)
        col = QVBoxLayout()
        self.title = QLabel("")
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size: 15px; font-weight: bold;")
        col.addWidget(self.title)
        self.meta = QLabel("")
        self.meta.setObjectName("muted")
        self.meta.setStyleSheet("font-size: 11px;")
        self.meta.setWordWrap(True)
        col.addWidget(self.meta)
        self.chip = QLabel("")
        self.chip.hide()
        col.addWidget(self.chip, 0, Qt.AlignLeft)
        col.addStretch(1)
        row.addLayout(col, 1)
        lay.addLayout(row)
        lay.addSpacing(8)
        cap = QLabel(T("Subtitle candidates"))
        cap.setStyleSheet("font-size: 13px; font-weight: bold;")
        lay.addWidget(cap)
        self.tree = make_tree(("rel", "match", "why"), (T("Subtitle / release"), T("Match"), T("Why")))
        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(1, 60)
        self.tree.header().setStretchLastSection(True)
        self.tree.itemDoubleClicked.connect(lambda *_: self.download())
        lay.addWidget(self.tree, 1)
        bar = QHBoxLayout()
        self.dl_btn = QPushButton(T("Download"))
        self.dl_btn.setObjectName("primary")
        self.dl_btn.clicked.connect(self.download)
        bar.addWidget(self.dl_btn)
        pv = QPushButton(T("Preview"))
        pv.clicked.connect(self.preview)
        bar.addWidget(pv)
        self.status = QLabel("")
        bar.addWidget(self.status, 1)
        lay.addLayout(bar)
        self.items, self.info, self.dl = {}, None, None

    def show_video(self, info):
        self.info = info
        self.fname.setText(os.path.basename(info.path))
        self.title.setText(info.label())
        self.meta.setText(str(info.year or ""))
        self.tree.clear()
        self.items = {}
        self.chip.hide()
        self.poster.setPixmap(QPixmap())
        self.poster.setText(os.path.splitext(os.path.basename(info.path))[1].strip(".").upper())
        self.status.setText(T("Looking for candidates..."))
        self.dl, _skipped = self.app.make_downloader(self.page.lang.currentText(), lambda m: None)
        self.app.bg(lambda: self.dl.list_candidates(info), self.loaded)
        if info.title:
            self.app.bg(lambda: self._details(info), self._details_loaded)

    def _details(self, info):
        d = self.app.details_cache.get(info.title)
        if d is None:
            d = C.imdb_details(info.title, info.year) or {}
            img = None
            if d.get("poster"):
                try:
                    img = C.http_get(d["poster"])
                except Exception as e:
                    dlog(f"poster failed: {e}")
            d = dict(d, _img=img)
            self.app.details_cache[info.title] = d
        return d

    def _details_loaded(self, d, err):
        if err or d is None or self.info is None:
            return
        if d.get("_img"):
            pm = QPixmap()
            pm.loadFromData(d["_img"])
            if not pm.isNull():
                self.poster.setPixmap(pm.scaled(120, 178, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if d.get("title"):
            year = d.get("year") or ""
            self.title.setText(f"{d['title']} ({year})" if year else d["title"])
        meta = " \u00b7 ".join(x for x in (d.get("type", ""), (d.get("cast") or "")[:48]) if x)
        if meta:
            self.meta.setText(meta)

    def loaded(self, res, err):
        if err:
            self.status.setText("Error: " + friendly_error(err))
            return
        items, errs = res
        for i, it in enumerate(items):
            c = it["cand"]
            row = QTreeWidgetItem([c.get("release_name", ""),
                                   "file hash" if c.get("hash") else ("good" if c["quality"] >= C.WEAK else "weak"),
                                   c.get("reason", "")])
            tag_row(row, "ok" if (c.get("hash") or c["quality"] >= C.WEAK) else "review")
            self.tree.addTopLevelItem(row)
            self.items[str(i)] = it
            row.setData(0, Qt.UserRole, str(i))
        msg = f"{len(items)} candidate(s)"
        if errs:
            msg += "   |   " + "; ".join(errs)
        self.status.setText(msg)
        if items:
            c = items[0]["cand"]
            ok = c.get("hash") or c["quality"] >= C.WEAK
            self.chip.setText(("\u2713 " if ok else "\u26a0 ") +
                              ("Exact match - file hash" if c.get("hash") else ("Good match" if ok else "Weak match")))
            self.chip.setObjectName("chip_ok" if ok else "chip_warn")
            self.chip.style().unpolish(self.chip)
            self.chip.style().polish(self.chip)
            self.chip.show()

    def current(self):
        sel = self.tree.selectedItems()
        return self.items.get(sel[0].data(0, Qt.UserRole)) if sel else None

    def preview(self):
        it = self.current()
        if not it or not self.dl:
            return
        self.status.setText("Loading preview...")
        self.app.bg(lambda: self.dl.preview_item(self.info, it), self._shown)

    def _shown(self, text, err):
        if err:
            self.status.setText("Error: " + friendly_error(err))
        else:
            self.status.setText("")
            TextDialog(self, T("Preview"), text).exec()

    def download(self):
        it = self.current()
        if not it or not self.dl:
            return
        self.status.setText("Saving...")
        self.app.bg(lambda: self.dl.save_item(self.info, it), self._saved)

    def _saved(self, path, err):
        if err:
            self.status.setText("Error: " + friendly_error(err))
            return
        self.status.setText("")
        self.page.set_status(self.info.path, f"OK (manual)  ->  {os.path.basename(path)}", "ok")



# ------------------------------------------------------------ Auto Folder page
class AutoPage(Page):
    def __init__(self, app):
        super().__init__(app)
        self.videos, self.base, self.running = [], None, False
        self.stop_flag = threading.Event()
        self.attempted = {}
        self.dls = []

        split = QSplitter(Qt.Horizontal)
        leftw = QWidget()
        lay = QVBoxLayout(leftw)
        lay.setContentsMargins(0, 0, 0, 0)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(split)
        split.addWidget(leftw)
        self.details = DetailsPanel(self)
        split.addWidget(self.details)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 0)
        leftw.setMinimumWidth(480)
        self.details.setMinimumWidth(300)
        split.setSizes([920, 380])
        self.split = split
        top = QHBoxLayout()
        top.addWidget(QLabel(T("Movie / series folder:")))
        arg = sys.argv[1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]) else None
        if getattr(sys, "frozen", False):
            start = arg or app.cfg.get("last_folder") or os.path.join(os.path.expanduser("~"), "Videos")
        else:
            start = arg or C.app_dir()
        self.folder = QLineEdit(start)
        top.addWidget(self.folder, 1)
        for text, fn in ((T("Browse..."), self.browse), (T("Scan"), self.scan)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            top.addWidget(b)
        lay.addLayout(top)

        opts = QHBoxLayout()
        opts.addWidget(QLabel(T("Language:")))
        self.lang = QComboBox()
        self.lang.addItems(list(LANGS))
        self.lang.setCurrentText(app.cfg.get("language", "English"))
        self.lang.currentTextChanged.connect(lambda _t: self.refresh_status())
        opts.addWidget(self.lang)
        self.subfolders = QCheckBox(T("Include subfolders"))
        self.subfolders.setChecked(True)
        self.subfolders.toggled.connect(lambda _on: self.scan())
        opts.addWidget(self.subfolders)
        self.overwrite = QCheckBox(T("Overwrite existing"))
        opts.addWidget(self.overwrite)
        opts.addStretch(1)
        lay.addLayout(opts)
        lay.addWidget(options_row(app))

        w = QHBoxLayout()
        self.watch = QCheckBox(T("Watch this folder for new videos"))
        w.addWidget(self.watch)
        hint = QLabel(T("Drop folders or video files anywhere in this window"))
        hint.setObjectName("muted")
        w.addWidget(hint, 1)
        lay.addLayout(w)

        self.tree = make_tree(("file", "detected", "status"), (T("Video file"), T("Detected as"), T("Status")))
        self.tree.itemDoubleClicked.connect(lambda *_: self.pick_manual())
        lay.addWidget(self.tree, 1)

        bar = QHBoxLayout()
        self.go_btn = QPushButton(T("Download subtitles"))
        self.go_btn.setObjectName("primary")
        self.go_btn.clicked.connect(self.start)
        bar.addWidget(self.go_btn)
        self.stop_btn = QPushButton(T("Stop"))
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(lambda: self.stop_flag.set())
        bar.addWidget(self.stop_btn)
        pick = QPushButton(T("Pick manually..."))
        pick.clicked.connect(self.pick_manual)
        bar.addWidget(pick)
        self.progress = QProgressBar()
        bar.addWidget(self.progress, 1)
        self.count = QLabel("")
        bar.addWidget(self.count)
        lay.addLayout(bar)

        self.stats = QLabel("")
        self.stats.setObjectName("muted")
        lay.addWidget(self.stats)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        self.log.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        lay.addWidget(self.log)

        self.watch_timer = QTimer(self)
        self.watch_timer.timeout.connect(self.watch_tick)
        self.watch_timer.start(60000)
        self.tree.itemSelectionChanged.connect(self.on_select)

    def on_select(self):
        sel = self.tree.selectedItems()
        info = next((v for v in self.videos if v.path == sel[0].data(0, Qt.UserRole)), None) if sel else None
        if info:
            self.details.show_video(info)

    # -- list handling
    def on_show(self):
        if not self.videos:
            self.scan()

    def write(self, msg):
        self.log.appendPlainText(str(msg))

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, APP_NAME, self.folder.text() or None)
        if d:
            self.folder.setText(d)
            self.scan()

    def scan(self):
        folder = self.folder.text().strip()
        if os.path.isdir(folder):
            self.set_paths([folder])

    def set_paths(self, paths):
        """Used by Scan, the right-click menu argument and drag & drop."""
        paths = [p for p in paths if os.path.exists(p)]
        vids = C.videos_from_paths(paths, self.subfolders.isChecked())
        self.base = paths[0] if len(paths) == 1 and os.path.isdir(paths[0]) else None
        if len(paths) == 1:
            self.folder.setText(paths[0])
            if os.path.isdir(paths[0]):
                self.app.cfg["last_folder"] = paths[0]
        else:
            self.folder.setText(f"{len(paths)} items")
        self.videos = [VideoInfo(p) for p in vids]
        self.tree.clear()
        for info in self.videos:
            shown = os.path.relpath(info.path, self.base) if self.base else os.path.basename(info.path)
            row = QTreeWidgetItem([shown, info.label(), ""])
            row.setData(0, Qt.UserRole, info.path)
            self.tree.addTopLevelItem(row)
        self.refresh_status()
        self.count.setText(f"{len(self.videos)} video(s)")
        self.write(f"Found {len(self.videos)} video file(s)")

    def _row(self, path):
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.data(0, Qt.UserRole) == path:
                return it
        return None

    def refresh_status(self):
        suffix = LANGS[self.lang.currentText()]["suffix"]
        for info in self.videos:
            row = self._row(info.path)
            if row and row.text(2) in ("", T("waiting"), T("has subtitle")):
                row.setText(2, T("has subtitle") if C.existing_sub(info.path, suffix) else T("waiting"))

    def set_status(self, path, text, tag=""):
        row = self._row(path)
        if row:
            row.setText(2, text)
            tag_row(row, tag)

    # -- downloading
    def start(self, todo=None, quiet=False):
        if self.running:
            return
        lang = self.lang.currentText()
        langs = [lang]
        second = self.app.cfg.get("language2", "")
        if second and second in LANGS and second != lang:
            langs.append(second)
        dls, skipped = [], []
        for lg in langs:
            dl, sk = self.app.make_downloader(lg, lambda m: self.ui(self.write, m))
            skipped = sk
            if dl.providers:
                dls.append(dl)
        if skipped:
            self.write("Skipped (not set up in Settings > Sources): " + ", ".join(skipped))
        if not dls:
            if not quiet:
                QMessageBox.information(self, APP_NAME, "No usable source. Open Settings > Sources, enable a source "
                                        "and add its key if it needs one.")
            return
        if not self.videos:
            self.scan()
        if todo is None:
            sel = {i.data(0, Qt.UserRole) for i in self.tree.selectedItems()}
            todo = [v for v in self.videos if (not sel or v.path in sel)]
        if not todo:
            return
        self.app.cfg["language"] = lang
        C.save_config(self.app.cfg)
        self.dls = dls
        self.running = True
        self.stop_flag.clear()
        self.go_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setRange(0, len(todo))
        self.progress.setValue(0)
        threading.Thread(target=self.run, args=(dls, todo, self.overwrite.isChecked()), daemon=True).start()

    def run(self, dls, todo, overwrite):
        ok = 0
        rank = {"error": 4, "review": 3, "none": 2, "ok": 1, "skip": 0}
        for i, info in enumerate(todo, 1):
            if self.stop_flag.is_set():
                break
            self.ui(self.set_status, info.path, T("searching..."), "")
            results = []
            for dl in dls:
                try:
                    results.append((dl.suffix,) + dl.fetch_for(info, overwrite))
                except Exception as e:
                    dlog(f"auto error: {e!r}")
                    results.append((dl.suffix, "error", "error: " + friendly_error(e)))
            worst = max(results, key=lambda r: rank[r[1]])[1]
            text = results[0][2] if len(results) == 1 else "  |  ".join(f"{s}: {m}" for s, _c, m in results)
            tag = {"ok": "ok", "skip": "", "review": "review"}.get(worst, "bad")
            ok += sum(r[1] == "ok" for r in results)
            if worst in ("none", "error", "review"):
                self.attempted[info.path] = time.time()
            self.ui(self.set_status, info.path, text, tag)
            self.ui(self.write, f"{info.label()}: {text}")
            self.ui(lambda n=i: self.progress.setValue(n))
            self.ui(self.show_stats)
            if all(r[2] == "error: no valid API key / login" for r in results):
                break
        self.ui(self.finished, ok, len(todo))

    def show_stats(self):
        txt = "  \u00b7  ".join(t for t in (d.stats_text() for d in self.dls) if t)
        self.stats.setText((T("Sources:") + " " + txt) if txt else "")

    def finished(self, ok, total):
        self.running = False
        self.write(f"Finished: {ok} subtitle(s) downloaded for {total} video(s).")
        self.go_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    # -- manual pick
    def pick_manual(self):
        sel = self.tree.selectedItems()
        if not sel:
            return
        info = next((v for v in self.videos if v.path == sel[0].data(0, Qt.UserRole)), None)
        if not info:
            return
        dl, _skipped = self.app.make_downloader(self.lang.currentText(), lambda m: None)
        if not dl.providers:
            QMessageBox.information(self, APP_NAME, "No usable source. Check Settings > Sources.")
            return
        PickDialog(self, info, dl)

    # -- watch mode
    def watch_tick(self):
        try:
            if self.watch.isChecked() and not self.running:
                folder = self.folder.text().strip()
                if os.path.isdir(folder):
                    known = {v.path for v in self.videos}
                    fresh = [VideoInfo(p) for p in C.find_videos(folder, self.subfolders.isChecked()) if p not in known]
                    for info in fresh:
                        self.videos.append(info)
                        row = QTreeWidgetItem([os.path.relpath(info.path, folder), info.label(), T("waiting")])
                        row.setData(0, Qt.UserRole, info.path)
                        self.tree.addTopLevelItem(row)
                    suffix = LANGS[self.lang.currentText()]["suffix"]
                    now = time.time()
                    todo = [v for v in self.videos if not C.existing_sub(v.path, suffix)
                            and now - self.attempted.get(v.path, 0) > 6 * 3600
                            and now - os.path.getmtime(v.path) > 60]
                    if todo:
                        self.write(f"Watch: {len(todo)} new video(s) without subtitles")
                        self.start(todo=todo, quiet=True)
        except Exception as e:
            dlog(f"watch error: {e!r}")


# ----------------------------------------------------------------- Search page
class SearchPage(Page):
    def __init__(self, app):
        super().__init__(app)
        self.items, self.subs, self.cur = {}, {}, None
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.src = QComboBox()
        self.src.addItems(SOURCE_ORDER)
        top.addWidget(self.src)
        self.box = QLineEdit()
        self.box.setPlaceholderText(T("Search Movie\\Series by Name or IMDB id"))
        self.box.returnPressed.connect(self.run_search)
        top.addWidget(self.box, 1)
        go = QPushButton(T("Search"))
        go.clicked.connect(self.run_search)
        top.addWidget(go)
        lay.addLayout(top)

        split = QSplitter(Qt.Vertical)
        upper = QSplitter(Qt.Horizontal)
        self.tree = make_tree(("title", "source"), (T("Results"), T("Source")))
        self.tree.setColumnWidth(0, 460)
        self.tree.setMinimumWidth(320)
        self.tree.itemSelectionChanged.connect(self.pick_item)
        upper.addWidget(self.tree)
        card = QFrame()
        card.setMinimumWidth(180)
        cl = QVBoxLayout(card)
        self.poster = QLabel()
        self.poster.setAlignment(Qt.AlignCenter)
        cl.addWidget(self.poster)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("font-size: 12px;")
        cl.addWidget(self.info, 1)
        upper.addWidget(card)
        upper.setStretchFactor(0, 1)
        upper.setStretchFactor(1, 0)
        upper.setMinimumHeight(200)
        split.addWidget(upper)
        self.subtree = make_tree(("release", "lang", "author"), (T("Subtitle / release"), T("Language"), T("Uploader")))
        self.subtree.setColumnWidth(0, 520)
        self.subtree.setMinimumHeight(140)
        self.subtree.itemDoubleClicked.connect(lambda *_: self.download())
        split.addWidget(self.subtree)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([420, 260])
        lay.addWidget(split, 1)
        self._split_v = split
        self._split_h = upper

        lay.addWidget(options_row(app, bom=False))
        bar = QHBoxLayout()
        bar.addWidget(QLabel(T("Language:")))
        self.lang = QComboBox()
        self.lang.addItems(list(LANGS))
        self.lang.setCurrentText(app.cfg.get("language", "English"))
        self.lang.currentTextChanged.connect(lambda _t: self.pick_item())
        bar.addWidget(self.lang)
        for text, fn in ((T("Download"), self.download), (T("Preview"), self.preview),
                         (T("Open in browser"), self.open_web)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            bar.addWidget(b)
        self.status = QLabel("")
        bar.addWidget(self.status, 1)
        lay.addLayout(bar)

    def on_show(self):
        self.box.setFocus()

    def say(self, text):
        self.status.setText(text)

    def run_search(self):
        q = self.box.text().strip()
        if not q:
            self.say("Type a movie / series name or an IMDb id (tt1234567)")
            return
        src = self.app.source(self.src.currentText())
        self.say(f"Searching {src.name}...")
        self.tree.clear()
        self.subtree.clear()
        self.bg(lambda: src.search(q), self.on_results)

    def on_results(self, res, err):
        self.tree.clear()
        self.subtree.clear()
        self.items, self.cur = {}, None
        if err:
            self.say("Error: " + friendly_error(err))
            return
        for i, it in enumerate(res or []):
            row = QTreeWidgetItem([it["title"], it.get("source", "")])
            row.setData(0, Qt.UserRole, str(i))
            self.tree.addTopLevelItem(row)
            self.items[str(i)] = it
        self.say(f"{len(self.items)} result(s). Click one to list its subtitles." if self.items
                 else "No results. Try the Test button in Settings > Sources to check this site.")

    def pick_item(self):
        sel = self.tree.selectedItems()
        if not sel:
            return
        it = self.items.get(sel[0].data(0, Qt.UserRole))
        if not it:
            return
        self.cur = it
        lang = self.lang.currentText()
        src = self.app.source(it["source"])
        self.say(f"Loading {lang} subtitles...")
        self.subtree.clear()
        self.bg(lambda: src.subs(it, lang), lambda r, e, it=it: self.on_subs(it, r, e))
        self.bg(lambda: self.load_details(it), lambda r, e, it=it: self.on_details(it, r, e))

    def on_subs(self, it, res, err):
        if it is not self.cur:
            return
        self.subtree.clear()
        self.subs = {}
        if err:
            self.say("Error: " + friendly_error(err))
            return
        for i, s in enumerate(res or []):
            row = QTreeWidgetItem([s.get("release", ""), s.get("lang", ""), s.get("author", "")])
            row.setData(0, Qt.UserRole, str(i))
            self.subtree.addTopLevelItem(row)
            self.subs[str(i)] = s
        self.say(f"{len(self.subs)} subtitle(s). Double-click or press Download." if self.subs
                 else "No subtitles listed for this language.")

    # -- poster + details card (IMDb public data; Qt renders posters natively)
    def load_details(self, it):
        d = self.app.details_cache.get(it["title"])
        if d is None:
            d = C.imdb_details(it["title"], it.get("year")) or {}
            img = None
            if d.get("poster"):
                try:
                    img = C.http_get(d["poster"])
                except Exception as e:
                    dlog(f"poster failed: {e}")
            d = dict(d, _img=img)
            self.app.details_cache[it["title"]] = d
        return d

    def on_details(self, it, d, err):
        if it is not self.cur or err or d is None:
            return
        self.poster.clear()
        if d.get("_img"):
            pm = QPixmap()
            pm.loadFromData(d["_img"])
            if not pm.isNull():
                self.poster.setPixmap(pm.scaled(170, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        if d.get("title"):
            self.info.setText(f"{d['title']} ({d.get('year') or '?'})\n{d.get('type', '')}\n\n"
                              f"{d.get('cast', '')}\n\n{d.get('id', '')}")
        else:
            self.info.setText("")

    # -- actions
    def _picked(self):
        return [self.subs[i.data(0, Qt.UserRole)] for i in self.subtree.selectedItems()
                if i.data(0, Qt.UserRole) in self.subs]

    def download(self):
        picked = self._picked()
        if not picked or not self.cur:
            self.say("Select one or more subtitles first.")
            return
        dest = self.app.get_dest(self)
        if not dest:
            return
        src = self.app.source(self.cur["source"])
        lang, opts = self.lang.currentText(), self.app.clean_opts()
        extract, z = self.app.cfg.get("extract", True), self.app.sevenzip()

        def work():
            msgs = []
            for s in picked:
                name, data = src.fetch(s)
                msgs.append(C.save_blob(data, name, dest, lang, opts, extract, z))
            return msgs

        self.say("Downloading...")
        self.bg(work, lambda r, e: self.say(("Error: " + friendly_error(e)) if e else f"{r[-1]}   ->  {dest}"))

    def preview(self):
        picked = self._picked()
        if not picked or not self.cur:
            self.say("Select a subtitle to preview.")
            return
        src, s = self.app.source(self.cur["source"]), picked[0]
        lang, opts, z = self.lang.currentText(), self.app.clean_opts(), self.app.sevenzip()
        self.say("Loading preview...")

        def work():
            name, data = src.fetch(s)
            return C.preview_text(data, name, lang, opts, z)

        def done(text, err):
            if err:
                self.say("Error: " + friendly_error(err))
            else:
                self.say("")
                TextDialog(self, T("Preview"), text).exec()
        self.bg(work, done)

    def open_web(self):
        if self.cur:
            webbrowser.open(self.cur.get("url") or f"https://www.google.com/search?q={self.cur['title']}+subtitles")


# ------------------------------------------------------------ Subtitle Tools
class ToolsPage(Page):
    FPS = ["", "23.976", "24", "25", "29.97", "30"]

    def __init__(self, app):
        super().__init__(app)
        lay = QVBoxLayout(self)
        grid = QGridLayout()
        grid.addWidget(QLabel(T("Subtitle file:")), 0, 0)
        self.path = QLineEdit()
        grid.addWidget(self.path, 0, 1)
        b = QPushButton(T("Browse..."))
        b.clicked.connect(self.browse)
        grid.addWidget(b, 0, 2)
        grid.addWidget(QLabel(T("Shift timing (ms):")), 1, 0)
        row = QHBoxLayout()
        self.shift = QLineEdit("0")
        self.shift.setMaximumWidth(90)
        row.addWidget(self.shift)
        for d in (-1000, -500, 500, 1000):
            nb = QPushButton(f"{d:+d}")
            nb.clicked.connect(lambda _c, d=d: self.nudge(d))
            row.addWidget(nb)
        row.addStretch(1)
        grid.addLayout(row, 1, 1)
        grid.addWidget(QLabel(T("Frame rate: from")), 2, 0)
        row = QHBoxLayout()
        self.f_from, self.f_to = QComboBox(), QComboBox()
        for cb in (self.f_from, self.f_to):
            cb.setEditable(True)
            cb.addItems(self.FPS)
            cb.setMaximumWidth(100)
            row.addWidget(cb)
        row.addWidget(QLabel("  " + T("to") + "  "))
        row.addStretch(1)
        grid.addLayout(row, 2, 1)
        self.over = QCheckBox(T("Replace the original (keeps a .bak copy)"))
        grid.addWidget(self.over, 3, 1)
        lay.addLayout(grid)
        lay.addWidget(options_row(app))
        ap = QPushButton(T("Apply"))
        ap.clicked.connect(self.apply)
        lay.addWidget(ap, alignment=Qt.AlignLeft if not UI["rtl"] else Qt.AlignRight)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        lay.addWidget(sep)
        head = QLabel(T("Rename video files to clean names:"))
        head.setStyleSheet("font-weight: bold;")
        lay.addWidget(head)
        row = QHBoxLayout()
        self.rn_folder = QLineEdit()
        row.addWidget(self.rn_folder, 1)
        bf = QPushButton(T("Browse..."))
        bf.clicked.connect(self.browse_folder)
        row.addWidget(bf)
        lay.addLayout(row)
        row = QHBoxLayout()
        for text, fn in ((T("Preview renames"), self.preview_renames), (T("Apply renames"), self.apply_renames),
                         (T("Undo last rename"), self.undo_renames)):
            rb = QPushButton(text)
            rb.clicked.connect(fn)
            row.addWidget(rb)
        row.addStretch(1)
        lay.addLayout(row)

        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        lay.addStretch(1)

    def browse(self):
        p, _ = QFileDialog.getOpenFileName(self, APP_NAME, "", "Subtitles (*.srt *.ass *.ssa *.vtt);;All files (*.*)")
        if p:
            self.path.setText(p)

    def nudge(self, d):
        try:
            v = int(float(self.shift.text() or 0))
        except ValueError:
            v = 0
        self.shift.setText(str(v + d))

    def apply(self):
        p = self.path.text().strip()
        if not p or not os.path.isfile(p):
            self.msg.setText(T("Pick a subtitle file first."))
            return
        try:
            shift = int(float(self.shift.text() or 0))
            ff = float(self.f_from.currentText()) if self.f_from.currentText() else None
            ft = float(self.f_to.currentText()) if self.f_to.currentText() else None
        except ValueError:
            self.msg.setText("Shift and frame rates must be numbers.")
            return
        lang, opts, over = self.app.cfg.get("language", "English"), self.app.clean_opts(), self.over.isChecked()
        self.bg(lambda: C.transform_file(p, shift, ff, ft, lang, opts, over),
                lambda r, e: self.msg.setText(("Error: " + friendly_error(e)) if e else r[1]))

    # -- rename videos
    def browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, APP_NAME)
        if d:
            self.rn_folder.setText(d)

    def _rename_plan(self):
        folder = self.rn_folder.text().strip()
        if not folder or not os.path.isdir(folder):
            self.msg.setText(T("Pick a folder with videos first."))
            return None
        return C.plan_renames([folder])

    def preview_renames(self):
        plan = self._rename_plan()
        if plan is None:
            return
        if not plan:
            self.msg.setText(T("Nothing to rename - all names already look clean."))
            return
        text = "\n".join(f"{os.path.basename(o)}\n   ->  {os.path.basename(n)}" for o, n in plan)
        TextDialog(self, T("Rename preview") + f" ({len(plan)})", text).exec()

    def apply_renames(self):
        plan = self._rename_plan()
        if not plan:
            self.msg.setText(T("Nothing to rename."))
            return
        done = C.apply_renames(plan)
        self.msg.setText(T("Renamed") + f" {len(done)} " + T("file(s). Use Undo to restore."))

    def undo_renames(self):
        restored = C.undo_last_rename()
        self.msg.setText((T("Restored") + f" {len(restored)} " + T("file(s)."))
                         if restored else T("Nothing to undo."))


# --------------------------------------------------------------- Settings page
SOURCE_NOTES = {
    "OpenSubtitles": "official API · needs API key + free account · supports file-hash matching",
    "SubSource": "official API · needs free API key",
    "Subf2m": "unofficial (web scraping) · off by default · may be blocked",
}
UI_LANGS = {"English": "en", "\u0627\u0644\u0639\u0631\u0628\u064a\u0629": "ar"}
THEMES = {"System": "system", "Light": "light", "Dark": "dark"}


class SettingsPage(Page):
    def __init__(self, app):
        super().__init__(app)
        c = app.cfg
        lay = QVBoxLayout(self)
        self.nb = QTabWidget()
        lay.addWidget(self.nb, 1)
        tabs = {}
        for key, title in (("general", "General"), ("sources", "Sources"), ("subs", "Subtitles"),
                           ("arch", "Archives"), ("adv", "Advanced"), ("about", "About")):
            f = QWidget()
            fl = QVBoxLayout(f)
            fl.setAlignment(Qt.AlignTop)
            self.nb.addTab(f, T(title))
            tabs[key] = fl

        # ---- General
        g = tabs["general"]
        self.ui_lang = QComboBox()
        self.ui_lang.addItems(list(UI_LANGS))
        self.ui_lang.setCurrentText(next(k for k, v in UI_LANGS.items() if v == c.get("ui_lang", "en")))
        self._form(g, T("Interface language"), self.ui_lang)
        self.theme = QComboBox()
        self.theme.addItems(list(THEMES))
        self.theme.setCurrentText(next(k for k, v in THEMES.items() if v == c.get("theme", "system")))
        self._form(g, T("Theme"), self.theme)
        self.lang = QComboBox()
        self.lang.addItems(list(LANGS))
        self.lang.setCurrentText(c.get("language", "English"))
        self._form(g, T("Default language"), self.lang)
        row = QHBoxLayout()
        self.dest = QLineEdit(c.get("dest") or os.path.join(os.path.expanduser("~"), "Downloads"))
        row.addWidget(self.dest, 1)
        bd = QPushButton(T("Browse..."))
        bd.clicked.connect(self.pick_dest)
        row.addWidget(bd)
        self._form(g, T("Download folder"), row)
        self.ask = QCheckBox(T("Ask where to save every time"))
        self.ask.setChecked(c.get("ask_dest", False))
        g.addWidget(self.ask)
        self.extract = QCheckBox(T("Extract .zip files after download"))
        self.extract.setChecked(c.get("extract", True))
        g.addWidget(self.extract)
        self.updates = QCheckBox(T("Check for updates on start"))
        self.updates.setChecked(c.get("check_updates", True))
        g.addWidget(self.updates)

        # ---- Sources
        s = tabs["sources"]
        self.order = C.ordered_sources(c)
        on = set(C.enabled_sources(c))
        self.enabled = {}
        self.status_lbls, self.status = {}, {}
        self.rows = QVBoxLayout()
        s.addLayout(self.rows)
        self.build_rows()
        note = QLabel(T("Unofficial sources scrape websites: they can break when a site changes, "
                        "may be blocked, and stay off until you enable them."))
        note.setObjectName("muted")
        note.setWordWrap(True)
        s.addWidget(note)
        cred = QGridLayout()
        ch = QLabel(T("Credentials"))
        ch.setStyleSheet("font-weight: bold;")
        cred.addWidget(ch, 0, 0, 1, 3)
        self.ss_key = QLineEdit(C.get_secret(c, "subsource_key"))
        self.os_key = QLineEdit(C.get_secret(c, "os_key"))
        self.os_user = QLineEdit(c.get("os_user", ""))
        self.os_pass = QLineEdit(C.get_secret(c, "os_pass"))
        for i, (label, w, secret, url) in enumerate((
                ("SubSource API key", self.ss_key, True, "https://subsource.net"),
                ("OpenSubtitles API key", self.os_key, True, "https://www.opensubtitles.com/consumers"),
                ("OpenSubtitles username", self.os_user, False, None),
                ("OpenSubtitles password", self.os_pass, True, None)), 1):
            cred.addWidget(QLabel(label), i, 0)
            if secret:
                w.setEchoMode(QLineEdit.Password)
            cred.addWidget(w, i, 1)
            if url:
                gb = QPushButton("Get key")
                gb.clicked.connect(lambda _c, u=url: webbrowser.open(u))
                cred.addWidget(gb, i, 2)
        store_note = ("Keys and the password are stored in the Windows Credential Manager, not in files."
                      if C.secrets_backend() == "keyring" else
                      "Keys and the password are stored on this PC in config.json (plain text). "
                      "Install the 'keyring' package to store them in the Windows Credential Manager instead.")
        sn = QLabel(store_note)
        sn.setObjectName("muted")
        sn.setWordWrap(True)
        cred.addWidget(sn, 5, 0, 1, 3)
        s.addLayout(cred)

        # ---- Subtitles
        t = tabs["subs"]
        for key, text in (("utf8", "Convert to UTF-8"), ("to_srt", "Convert to SRT"), ("ads", "Remove ads / watermarks"),
                          ("hi", "Remove hearing-impaired tags"), ("bom", "Add BOM (older TVs/players)")):
            cb = QCheckBox(T(text))
            cb.setChecked(app.clean_opts_state.get(key, False))
            cb.toggled.connect(lambda on, k=key: app.set_clean(k, on))
            t.addWidget(cb)
        self.use_hash = QCheckBox(T("Use file hash when possible (exact sync)"))
        self.use_hash.setChecked(c.get("use_hash", True))
        t.addWidget(self.use_hash)
        self.weak_save = QCheckBox(T("Save weak matches automatically"))
        self.weak_save.setChecked(c.get("weak_save", False))
        t.addWidget(self.weak_save)
        row = QHBoxLayout()
        row.addWidget(QLabel(T("Also download a second language:")))
        self.lang2 = QComboBox()
        self.lang2.addItems([T("None")] + list(LANGS))
        self.lang2.setCurrentText(c.get("language2") or T("None"))
        row.addWidget(self.lang2)
        row.addStretch(1)
        t.addLayout(row)

        # ---- Archives
        a = tabs["arch"]
        self.z_on = QCheckBox(T("Unpack RAR / 7z files with 7-Zip"))
        self.z_on.setChecked(c.get("sevenzip_on", True))
        a.addWidget(self.z_on)
        row = QHBoxLayout()
        row.addWidget(QLabel(T("7-Zip path")))
        self.z_path = QLineEdit(c.get("sevenzip_path", ""))
        row.addWidget(self.z_path, 1)
        bz = QPushButton(T("Browse..."))
        bz.clicked.connect(self.pick_7z)
        row.addWidget(bz)
        a.addLayout(row)
        self.z_lbl = QLabel("")
        self.z_lbl.setObjectName("muted")
        self.z_lbl.setWordWrap(True)
        a.addWidget(self.z_lbl)
        rc = QPushButton("Re-check")
        rc.clicked.connect(self.check_7z)
        a.addWidget(rc, alignment=Qt.AlignLeft if not UI["rtl"] else Qt.AlignRight)
        self.check_7z()

        # ---- Advanced
        d = tabs["adv"]
        h = QLabel(T("Site addresses (change them if a site moves)"))
        h.setStyleSheet("font-weight: bold;")
        d.addWidget(h)
        self.sites = {}
        saved = c.get("sites", {})
        defaults = {n: v[0] for n, v in C.SITES.items()}
        self.site_defaults = defaults
        form = QGridLayout()
        for i, (name, base) in enumerate(defaults.items()):
            form.addWidget(QLabel(name), i, 0)
            self.sites[name] = QLineEdit(saved.get(name) or base)
            form.addWidget(self.sites[name], i, 1)
        d.addLayout(form)
        row = QHBoxLayout()
        for text, fn in ((T("Reset site addresses"), self.reset_sites), (T("Open debug log"), self.open_log),
                         (T("Open data folder"), lambda: self.open_path(C.data_dir()))):
            bb = QPushButton(text)
            bb.clicked.connect(fn)
            row.addWidget(bb)
        row.addStretch(1)
        d.addLayout(row)
        info = QLabel("Portable mode: settings are kept in the 'data' folder next to SubGrab.exe." if C.is_portable()
                      else "Settings folder: " + C.data_dir() + "   (create an empty portable.txt next to SubGrab.exe for portable mode)")
        info.setObjectName("muted")
        info.setWordWrap(True)
        d.addWidget(info)

        # ---- About
        b = tabs["about"]
        if LOGO_PNG_B64:
            import base64
            pm = QPixmap()
            pm.loadFromData(base64.b64decode(LOGO_PNG_B64))
            lg = QLabel()
            lg.setPixmap(pm.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            b.addWidget(lg)
        ttl = QLabel(f"{APP_NAME} {VERSION}")
        ttl.setStyleSheet("font-size: 22px; font-weight: bold;")
        b.addWidget(ttl)
        desc = QLabel("Subtitle downloader - OpenSubtitles, SubSource, Subf2m and more.\n"
                      "GPL v3 licensed. 7-Zip (LGPL) is used for RAR/7z when available.\n"
                      "Icons: Phosphor Icons (MIT license) - phosphoricons.com")
        desc.setWordWrap(True)
        b.addWidget(desc)
        cu = QPushButton(T("Check for updates"))
        cu.clicked.connect(self.check_updates)
        b.addWidget(cu, alignment=Qt.AlignLeft if not UI["rtl"] else Qt.AlignRight)
        self.upd_lbl = QLabel("")
        b.addWidget(self.upd_lbl)
        if "YOUR-USERNAME" not in GITHUB_REPO:
            gh = QPushButton("Open GitHub page")
            gh.clicked.connect(lambda: webbrowser.open(f"https://github.com/{GITHUB_REPO}"))
            b.addWidget(gh, alignment=Qt.AlignLeft if not UI["rtl"] else Qt.AlignRight)

        # ---- bottom bar
        bar = QHBoxLayout()
        sv = QPushButton(T("Save"))
        sv.setObjectName("primary")
        sv.clicked.connect(self.save)
        bar.addWidget(sv)
        self.msg = QLabel("")
        bar.addWidget(self.msg, 1)
        self.restart_btn = QPushButton(T("Restart now"))
        self.restart_btn.clicked.connect(app.restart)
        self.restart_btn.hide()
        bar.addWidget(self.restart_btn)
        lay.addLayout(bar)

    def _form(self, layout, label, widget):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setMinimumWidth(150)
        row.addWidget(lbl)
        if isinstance(widget, QHBoxLayout):
            row.addLayout(widget, 1)
        else:
            row.addWidget(widget, 1)
        layout.addLayout(row)

    # -- sources tab
    def build_rows(self):
        while self.rows.count():
            it = self.rows.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.status_lbls = {}
        for i, name in enumerate(self.order):
            fr = QHBoxLayout()
            cb = QCheckBox(name)
            cb.setMinimumWidth(140)
            cb.setChecked(name in set(C.enabled_sources(self.app.cfg)) if name not in self.enabled else self.enabled[name])
            self.enabled[name] = cb
            fr.addWidget(cb)
            for arrow, d in (("\u2191", -1), ("\u2193", 1)):
                ab = QPushButton(arrow)
                ab.setMaximumWidth(34)
                ab.clicked.connect(lambda _c, i=i, d=d: self.move(i, d))
                fr.addWidget(ab)
            tb = QPushButton(T("Test"))
            tb.clicked.connect(lambda _c, n=name: self.test(n))
            fr.addWidget(tb)
            lbl = QLabel(self.status.get(name) or SOURCE_NOTES.get(name, ""))
            lbl.setObjectName("muted")
            lbl.setWordWrap(True)
            fr.addWidget(lbl, 1)
            self.status_lbls[name] = lbl
            w = QWidget()
            w.setLayout(fr)
            self.rows.addWidget(w)

    def move(self, i, d):
        j = i + d
        if 0 <= j < len(self.order):
            self.order[i], self.order[j] = self.order[j], self.order[i]
            for n, cb in self.enabled.items():
                self.enabled[n] = cb.isChecked()
            self.build_rows()

    def test(self, name):
        cfg = dict(self.app.cfg)
        cfg.update(self.collect())
        for k, w in (("subsource_key", self.ss_key), ("os_key", self.os_key), ("os_pass", self.os_pass)):
            C.set_secret(cfg, k, w.text())
        src = C.build_sources(cfg)[name]
        self.status[name] = "testing..."
        self.status_lbls[name].setText("testing...")

        def done(res, err):
            ok, msg = (False, friendly_error(err)) if err else res
            self.status[name] = ("\u2713 " if ok else "\u2717 ") + msg
            if name in self.status_lbls:
                try:
                    self.status_lbls[name].setText(self.status[name])
                except Exception:
                    pass
        self.app.bg(lambda: C.test_source(src), done)

    # -- misc tabs
    def pick_dest(self):
        d = QFileDialog.getExistingDirectory(self, APP_NAME, self.dest.text() or None)
        if d:
            self.dest.setText(d)

    def pick_7z(self):
        p, _ = QFileDialog.getOpenFileName(self, APP_NAME, "", "7z.exe (7z.exe);;All files (*.*)")
        if p:
            self.z_path.setText(p)
            self.check_7z()

    def check_7z(self):
        exe = C.find_7z(self.z_path.text().strip())
        bundled = os.path.isfile(os.path.join(getattr(sys, "_MEIPASS", ""), "7zip", "7z.exe"))
        if exe:
            self.z_lbl.setText(f"\u2713 Found: {exe}" + ("  (bundled with SubGrab)" if bundled else ""))
        else:
            self.z_lbl.setText("\u2717 7-Zip not found. Install it from 7-zip.org, or point to 7z.exe above. "
                               "RAR/7z downloads are skipped until then (zip and plain .srt always work).")

    def reset_sites(self):
        for n, v in self.site_defaults.items():
            self.sites[n].setText(v)

    def open_path(self, p):
        try:
            os.startfile(p)  # Windows
        except AttributeError:
            webbrowser.open("file://" + p)

    def open_log(self):
        p = os.path.join(C.data_dir(), "debug.log")
        if not os.path.exists(p):
            open(p, "a").close()
        self.open_path(p)

    def check_updates(self):
        self.upd_lbl.setText("Checking...")

        def done(res, err):
            if err:
                self.upd_lbl.setText("Could not check: " + friendly_error(err))
            elif res:
                self.upd_lbl.setText(f"Version {res[0]} is available: {res[1]}")
                webbrowser.open(res[1])
            else:
                self.upd_lbl.setText("You are up to date." if "YOUR-USERNAME" not in GITHUB_REPO
                                     else "Update checking is off until GITHUB_REPO is set in subgrab_core.py.")
        self.app.bg(C.check_update, done)

    # -- save
    def collect(self):
        lang2 = self.lang2.currentText()
        return {
            "language": self.lang.currentText(), "dest": self.dest.text(), "ask_dest": self.ask.isChecked(),
            "extract": self.extract.isChecked(), "check_updates": self.updates.isChecked(), "order": list(self.order),
            "enabled": {n: cb.isChecked() if isinstance(cb, QCheckBox) else bool(cb)
                        for n, cb in self.enabled.items()},
            "os_user": self.os_user.text().strip(),
            "use_hash": self.use_hash.isChecked(), "weak_save": self.weak_save.isChecked(),
            "language2": "" if lang2 in (T("None"), "None") else lang2,
            "sevenzip_on": self.z_on.isChecked(), "sevenzip_path": self.z_path.text().strip(),
            "sites": {n: w.text().strip() for n, w in self.sites.items() if w.text().strip() != self.site_defaults[n]},
        }

    def save(self):
        old = (self.app.cfg.get("ui_lang", "en"), self.app.cfg.get("theme", "system"))
        new_cfg = self.collect()
        new_cfg["ui_lang"] = UI_LANGS[self.ui_lang.currentText()]
        new_cfg["theme"] = THEMES[self.theme.currentText()]
        self.app.cfg.update(new_cfg)
        for name, w in (("subsource_key", self.ss_key), ("os_key", self.os_key), ("os_pass", self.os_pass)):
            C.set_secret(self.app.cfg, name, w.text())
        C.save_config(self.app.cfg)
        self.app.build_sources()
        changed = old != (new_cfg["ui_lang"], new_cfg["theme"])
        self.msg.setText(T("Saved.") + ("  " + T("Restart to apply language / theme changes.") if changed else ""))
        if changed:
            self.restart_btn.show()


# --------------------------------------------------------------------- the app
class App(QMainWindow):
    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.q = queue.Queue()
        self.details_cache = {}
        self.clean_opts_state = dict(DEFAULT_CLEAN, **cfg.get("clean", {}))
        self.srcs = {}
        self.build_sources()

        self.setWindowTitle(APP_NAME)
        self.resize(1140, 740)
        self.setMinimumSize(960, 620)
        if LOGO_PNG_B64:
            import base64
            pm = QPixmap()
            pm.loadFromData(base64.b64decode(LOGO_PNG_B64))
            if not pm.isNull():
                self.setWindowIcon(QIcon(pm))
        self.setAcceptDrops(True)

        root = QWidget()
        rootv = QVBoxLayout(root)
        rootv.setContentsMargins(0, 0, 0, 0)
        rootv.setSpacing(0)
        self.setCentralWidget(root)

        # ---- top toolbar
        tb = QFrame()
        tb.setObjectName("toolbar")
        tb.setFixedHeight(64)
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(12, 0, 12, 0)
        tl.setSpacing(6)
        if LOGO_PNG_B64:
            import base64
            pm = QPixmap()
            pm.loadFromData(base64.b64decode(LOGO_PNG_B64))
            lg = QLabel()
            lg.setPixmap(pm.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            tl.addWidget(lg)
        ttl = QLabel(APP_NAME)
        ttl.setObjectName("tb_title")
        tl.addWidget(ttl)
        tag = QLabel(T("find - fix - save subtitles"))
        tag.setObjectName("tb_tag")
        tl.addWidget(tag)
        tl.addSpacing(20)
        self.tb_buttons = {}

        def tool(key, icn, text, fn):
            b = QToolButton()
            b.setObjectName("toolbtn")
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            b.setText(text)
            b.setIconSize(QSize(20, 20))
            b.clicked.connect(fn)
            tl.addWidget(b)
            self.tb_buttons[key] = (b, icn)

        tool("update", "arrows-clockwise", T("Update sources"), self.update_sources)
        tool("find", "download-simple", T("Find subtitles"), lambda: self.show_page("search"))
        tool("rename", "broom", T("Rename && cleanup"), lambda: self.show_page("tools"))
        tool("activity", "list-bullets", T("Activity log"), lambda: self.show_page("auto"))
        tl.addStretch(1)
        self.theme_btn = QToolButton()
        self.theme_btn.setObjectName("themebtn")
        self.theme_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.theme_btn.setIconSize(QSize(15, 15))
        self.theme_btn.setFixedHeight(28)
        self.theme_btn.clicked.connect(self.toggle_theme)
        tl.addWidget(self.theme_btn)
        rootv.addWidget(tb)

        # ---- body: icon rail + content
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        rootv.addLayout(body, 1)
        rail = QFrame()
        rail.setObjectName("rail")
        rail.setFixedWidth(64)
        sl = QVBoxLayout(rail)
        sl.setContentsMargins(8, 10, 8, 10)
        sl.setSpacing(8)
        body.addWidget(rail)

        right = QFrame()
        right.setObjectName("panel")
        rl2 = QVBoxLayout(right)
        rl2.setContentsMargins(10, 8, 10, 0)
        self.banner = QPushButton("")
        self.banner.setObjectName("banner")
        self.banner.hide()
        rl2.addWidget(self.banner)
        self.stack = QStackedWidget()
        rl2.addWidget(self.stack)
        body.addWidget(right, 1)

        self.pages, self.navs = {}, {}

        def add(key, icn, text, factory, bottom=False):
            btn = QToolButton()
            btn.setObjectName("railbtn")
            btn.setFixedSize(48, 48)
            btn.setIconSize(QSize(22, 22))
            btn.setToolTip(T(text))
            btn.setProperty("active", False)
            btn.clicked.connect(lambda _c, k=key: self.show_page(k))
            if bottom:
                sl.addStretch(1)
            sl.addWidget(btn, 0, Qt.AlignHCenter)
            self.navs[key] = (btn, icn)
            page = factory()
            self.pages[key] = page
            self.stack.addWidget(page)

        add("auto", "folder-open", "Auto Folder", lambda: AutoPage(self))
        add("search", "magnifying-glass", "Search", lambda: SearchPage(self))
        add("tools", "broom", "Subtitle Tools", lambda: ToolsPage(self))
        add("set", "gear-six", "Settings", lambda: SettingsPage(self), bottom=True)

        # restore user-adjusted panel sizes
        from PySide6.QtCore import QByteArray
        self._persisted_splitters = {"auto_h": self.pages["auto"].split,
                                     "search_v": self.pages["search"]._split_v,
                                     "search_h": self.pages["search"]._split_h}
        for key, sp in self._persisted_splitters.items():
            st = self.cfg.get("splitters", {}).get(key)
            if st:
                sp.restoreState(QByteArray.fromBase64(st.encode("ascii")))

        # ---- status bar
        sb = QFrame()
        sb.setObjectName("statusbar")
        sb.setFixedHeight(28)
        sbl = QHBoxLayout(sb)
        sbl.setContentsMargins(12, 0, 12, 0)
        sbl.setSpacing(8)
        self.sb_status = QLabel(T("Ready"))
        self.sb_status.setObjectName("sb_text")
        sbl.addWidget(self.sb_status)
        self.sb_prog = QProgressBar()
        self.sb_prog.setObjectName("sb_prog")
        self.sb_prog.setFixedSize(200, 8)
        self.sb_prog.setTextVisible(False)
        self.sb_prog.setRange(0, 100)
        self.sb_prog.hide()
        sbl.addWidget(self.sb_prog)
        self.sb_pct = QLabel("")
        self.sb_pct.setObjectName("sb_text")
        sbl.addWidget(self.sb_pct)
        sbl.addStretch(1)
        self.sb_src = QLabel("")
        self.sb_src.setObjectName("sb_text")
        self.sb_src.setTextFormat(Qt.RichText)
        sbl.addWidget(self.sb_src)
        rootv.addWidget(sb)
        self._apply_icons()
        self.refresh_src_health()

        if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
            QTimer.singleShot(200, lambda: self.pages["auto"].set_paths([sys.argv[1]]))
        self.show_page("auto")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(80)
        if self.cfg.get("check_updates", True):
            QTimer.singleShot(3000, lambda: self.bg(C.check_update, self.on_update))

    # -- settings-derived helpers
    def build_sources(self):
        self.srcs = C.build_sources(self.cfg)

    def source(self, name):
        return self.srcs[name]

    def clean_opts(self):
        return dict(self.clean_opts_state)

    def set_clean(self, key, on):
        self.clean_opts_state[key] = bool(on)
        self.cfg["clean"] = self.clean_opts()
        C.save_config(self.cfg)

    def sevenzip(self):
        if not self.cfg.get("sevenzip_on", True):
            return None
        return C.find_7z(self.cfg.get("sevenzip_path", ""))

    def make_downloader(self, lang, log):
        provs, skipped = [], []
        for n in C.enabled_sources(self.cfg):
            s = self.srcs[n]
            if hasattr(s, "configured") and not s.configured():
                skipped.append(n)
            else:
                provs.append(C.AutoAdapter(s, lang))
        dl = C.Downloader(provs, lang, log, opts=self.clean_opts(), sevenzip=self.sevenzip(),
                          weak_save=self.cfg.get("weak_save", False), use_hash=self.cfg.get("use_hash", True))
        return dl, skipped

    def get_dest(self, parent=None):
        if self.cfg.get("ask_dest"):
            return QFileDialog.getExistingDirectory(parent or self, "Save subtitles to...") or None
        return self.cfg.get("dest") or os.path.join(os.path.expanduser("~"), "Downloads")

    # -- navigation
    def closeEvent(self, ev):
        try:
            from PySide6.QtCore import QByteArray
            self.cfg["splitters"] = {k: bytes(s.saveState().toBase64()).decode("ascii")
                                     for k, s in self._persisted_splitters.items()}
            C.save_config(self.cfg)
        except Exception:
            pass
        super().closeEvent(ev)

    def show_page(self, key):
        self._current = key
        for k, (b, icn) in self.navs.items():
            act = k == key
            b.setProperty("active", act)
            b.style().unpolish(b)
            b.style().polish(b)
            b.setIcon(icon(icn, P["selfg"] if act else P["rail_icon"], 22))
        self.stack.setCurrentWidget(self.pages[key])
        self.pages[key].on_show()

    def _apply_icons(self):
        for key, (b, icn) in self.tb_buttons.items():
            b.setIcon(icon(icn, P["tb_fg"], 18))
        dark = P["dark"]
        self.theme_btn.setIcon(icon("sun" if dark else "moon", "#E5C07B" if dark else P["tb_fg"], 15))
        self.theme_btn.setText(" Dark" if dark else " Light")

    def update_sources(self):
        self.build_sources()
        self.refresh_src_health()
        self.sb_status.setText(T("Sources updated"))

    def toggle_theme(self):
        self.cfg["theme"] = "light" if P["dark"] else "dark"
        C.save_config(self.cfg)
        configure_ui(self.cfg)
        QApplication.instance().setStyleSheet(qss())
        self._apply_icons()
        self.refresh_src_health()
        self.show_page(getattr(self, "_current", "auto"))

    def refresh_src_health(self):
        parts = []
        for name in C.ordered_sources(self.cfg):
            s = self.srcs.get(name)
            ok = s.configured() if hasattr(s, "configured") else True
            color = P["ok"] if ok else P["warn"]
            parts.append(f'<span style="color:{color}">\u25cf</span> <span style="color:#C0C0C0">{name}</span>')
        self.sb_src.setText(" &nbsp; ".join(parts))

    # -- events
    def on_update(self, res, err):
        if res and not err:
            self.banner.setText(f"SubGrab {res[0]} is available - click to download")
            self.banner.clicked.connect(lambda: webbrowser.open(res[1]))
            self.banner.show()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.show_page("auto")
            self.pages["auto"].set_paths(paths)

    def restart(self):
        try:
            args = [sys.executable] + ([] if getattr(sys, "frozen", False) else [os.path.abspath(sys.argv[0])])
            subprocess.Popen(args)
        finally:
            QApplication.quit()

    # -- threading helpers: GUI work only ever runs on the Qt thread
    def bg(self, fn, done):
        def work():
            try:
                res, err = fn(), None
            except Exception as e:
                dlog(f"background error: {e!r}")
                res, err = None, e
            self.q.put(("cb", done, res, err))
        threading.Thread(target=work, daemon=True).start()

    def ui(self, fn, *args):
        self.q.put(("call", fn, args))

    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                try:
                    m[1](m[2], m[3]) if m[0] == "cb" else m[1](*m[2])
                except Exception as e:
                    dlog(f"ui callback error: {e!r}")
        except queue.Empty:
            pass
        ap = self.pages.get("auto")
        if ap is not None and hasattr(ap, "progress"):
            if getattr(ap, "running", False):
                if not self.sb_prog.isVisible():
                    self.sb_prog.show()
                self.sb_prog.setValue(ap.progress.value())
                self.sb_pct.setText(f"{ap.progress.value()}%")
                cnt = ap.count.text()
                if cnt:
                    self.sb_status.setText(cnt)
            elif self.sb_prog.isVisible():
                self.sb_prog.hide()
                self.sb_prog.setValue(0)
                self.sb_pct.setText("")


def main():
    app_q = QApplication(sys.argv)
    cfg = C.load_config()
    configure_ui(cfg)
    if UI["rtl"]:
        app_q.setLayoutDirection(Qt.RightToLeft)
    app_q.setStyleSheet(qss())
    win = App(cfg)
    win.show()
    sys.exit(app_q.exec())


if __name__ == "__main__":
    main()
