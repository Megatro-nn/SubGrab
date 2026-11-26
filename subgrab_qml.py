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
SubGrab - Qt Quick (QML) interface. All logic lives in subgrab_core.py.

The QML view (qml/Main.qml) talks to the Bridge object below through
context properties, slots and signals. Background work runs on threads;
results reach the GUI through Qt signals (queued across threads).
"""
import os
import sys
import threading
import time
import webbrowser

from PySide6.QtCore import (QAbstractListModel, QModelIndex, QObject, Qt, QTimer,
                            Signal, Slot, Property, QUrl)
from PySide6.QtGui import QGuiApplication, QIcon, QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QFileDialog

import subgrab_core as C
from subgrab_core import (APP_NAME, DEFAULT_CLEAN, GITHUB_REPO, LANGS, SOURCE_ORDER, VERSION,
                          VideoInfo, dlog, friendly_error)
from subgrab_i18n import UI, T
from subgrab_icons import ICONS

try:
    from subgrab_assets import LOGO_PNG_B64
except Exception:  # pragma: no cover
    LOGO_PNG_B64 = ""

# ------------------------------------------------------------------ palettes
PALETTES = {
    "dark": dict(bg="#14121B", rail="#191724", card="#211E2E", cardBorder="#322E45", fg="#F3F2F8",
                 muted="#9B98AE", accent="#7C6CFF", accentSoft="#332D5C", onAccent="#FFFFFF",
                 ok="#2FC98A", okSoft="#1C3A2F", warn="#E5A83D", warnSoft="#42321B", bad="#F0616D",
                 badSoft="#46242B", info="#4FA3E8", infoSoft="#1E3044", input="#191724"),
    "light": dict(bg="#F3F3F8", rail="#FFFFFF", card="#FFFFFF", cardBorder="#E8E6F3", fg="#1C1B28",
                  muted="#73718C", accent="#6C5CE7", accentSoft="#EDEBFE", onAccent="#FFFFFF",
                  ok="#15915B", okSoft="#DDF3E7", warn="#A96F06", warnSoft="#FBEBCB", bad="#D64550",
                  badSoft="#FBE4E6", info="#2F7FC4", infoSoft="#DEEDF9", input="#F7F7FB"),
}
ICON_ROLES = ("fg", "muted", "accent", "onAccent", "ok", "warn", "bad", "info")
THEME_MODES = {"System": "system", "Light": "light", "Dark": "dark"}
UI_LANGS = {"English": "en", "\u0627\u0644\u0639\u0631\u0628\u064a\u0629": "ar"}
SOURCE_NOTES = {
    "OpenSubtitles": "official API · needs API key + free account · supports file-hash matching",
    "SubSource": "official API · needs free API key",
    "Podnapisi": "no key · web scraping, experimental",
    "Subf2m": "unofficial (web scraping) · off by default · may be blocked",
    "YIFY": "unofficial (web scraping) · off by default · movies only",
    "Subscene": "unofficial (community mirror) · off by default · address may change",
}
POSTER_COLORS = ["#1B2440", "#3A1518", "#1E3A33", "#33261A", "#2A2E48", "#2E1E2A", "#241F1A", "#1A2E33"]


def system_is_dark():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except Exception:
        return QGuiApplication.palette().window().color().lightness() < 128


class ListModel(QAbstractListModel):
    """Small dict-list model: roles are the keys of the dicts it holds."""

    def __init__(self, roles, parent=None):
        super().__init__(parent)
        self._names = list(roles)
        self._roles = {Qt.UserRole + 1 + i: n.encode("utf-8") for i, n in enumerate(self._names)}
        self._items = []

    def roleNames(self):
        return self._roles

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        i = role - Qt.UserRole - 1
        if 0 <= i < len(self._names) and 0 <= index.row() < len(self._items):
            return self._items[index.row()].get(self._names[i])
        return None

    def setItems(self, items):
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def updateRow(self, row, **kw):
        if 0 <= row < len(self._items):
            self._items[row].update(kw)
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)

    def itemAt(self, row):
        return self._items[row] if 0 <= row < len(self._items) else None


class Bridge(QObject):
    paletteChanged = Signal()
    iconsChanged = Signal()
    detailsChanged = Signal()
    statusChanged = Signal()
    progressChanged = Signal()
    sourcesChanged = Signal()
    toast = Signal(str)
    previewReady = Signal(str, str)          # title, text
    renamePreviewReady = Signal(str, int)    # text, count
    movieStatusChanged = Signal(str, str, str)   # path, text, tag
    logLine = Signal(str)
    downloadStateChanged = Signal()

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.details_cache = {}
        self.clean_opts_state = dict(DEFAULT_CLEAN, **cfg.get("clean", {}))
        self.srcs = {}
        self.videos, self.base, self.base_folder = [], None, None
        self.cur_video = None
        self.dls = []
        self._running = False
        self.stop_flag = threading.Event()
        self.attempted = {}
        self.search_items, self.sub_items = {}, {}
        self.cur_result = None
        self._palette_version = 0
        self._status = T("Ready")
        self._progress = -1.0
        self._folder = cfg.get("last_folder") or os.path.join(os.path.expanduser("~"), "Videos")

        self.movies = ListModel(("path", "title", "file", "status", "tag", "sel", "pc", "mtype"), self)
        self.candidates = ListModel(("idx", "release", "why", "badge", "badgeKind", "whyKind"), self)
        self.results = ListModel(("idx", "title", "source", "year", "pc"), self)
        self.subs = ListModel(("idx", "release", "lang", "author", "why", "badge", "badgeKind", "whyKind"), self)
        self.sources = ListModel(("name", "note", "enabled", "status", "statusKind"), self)
        self.build_sources()
        self._details = {"title": "", "meta": "", "fname": "", "chip": "", "chipKind": "ok", "poster": ""}

        self.watch_timer = QTimer(self)
        self.watch_timer.setInterval(60000)
        self.watch_timer.timeout.connect(self._watch_tick)
        self.watch_timer.start()
        self.movieStatusChanged.connect(self._on_movie_status)

    # ------------------------------------------------------------- palette
    def _dark(self):
        theme = self.cfg.get("theme", "system")
        return theme == "dark" or (theme == "system" and system_is_dark())

    def get_palette(self):
        return dict(PALETTES["dark" if self._dark() else "light"])

    palette = Property("QVariantMap", get_palette, notify=paletteChanged)

    @Slot(result=str)
    def themeMode(self):
        return self.cfg.get("theme", "system")

    @Slot(result=str)
    def themeLabel(self):
        return "Dark" if self._dark() else "Light"

    @Slot()
    def toggleTheme(self):
        self.setThemeMode("light" if self._dark() else "dark")

    @Slot(str)
    def setThemeMode(self, mode):
        self.cfg["theme"] = mode
        C.save_config(self.cfg)
        self._palette_version += 1
        self._regen_icons()
        self.paletteChanged.emit()
        self.iconsChanged.emit()

    # --------------------------------------------------------------- icons
    def _regen_icons(self):
        pal = self.get_palette()
        outdir = os.path.join(C.data_dir(), "iconcache")
        os.makedirs(outdir, exist_ok=True)
        self._icon_paths = {}
        for name in ICONS:
            for role in ICON_ROLES:
                svg = ICONS[name].replace('fill="currentColor"', f'fill="{pal[role]}"')
                p = os.path.join(outdir, f"{name}-{role}-{self._palette_version}.svg")
                with open(p, "w", encoding="utf-8") as f:
                    f.write(svg)
                self._icon_paths[(name, role)] = p

    @Slot(str, str, result=str)
    def icon(self, name, role):
        if not hasattr(self, "_icon_paths"):
            self._palette_version += 1
            self._regen_icons()
        p = self._icon_paths.get((name, role)) or self._icon_paths.get((name, "muted"))
        return QUrl.fromLocalFile(p).toString() if p else ""

    # ------------------------------------------------------------- helpers
    def _bg(self, fn, done):
        def work():
            try:
                res = fn()
                err = None
            except Exception as e:  # noqa: BLE001
                res, err = None, e
            from PySide6.QtCore import QMetaObject, Q_ARG
            QMetaObject.invokeMethod(self, "_deliver", Qt.QueuedConnection,
                                     Q_ARG("QVariant", done), Q_ARG("QVariant", res), Q_ARG("QVariant", err))
        threading.Thread(target=work, daemon=True).start()

    @Slot("QVariant", "QVariant", "QVariant")
    def _deliver(self, done, res, err):
        done(res, err)

    def _emit_toast(self, msg):
        self.toast.emit(msg)

    def _set_status(self, text):
        self._status = text
        self.statusChanged.emit()

    def get_statusText(self):
        return self._status

    statusText = Property(str, get_statusText, notify=statusChanged)

    def _set_progress(self, frac):
        self._progress = frac
        self.progressChanged.emit()

    def get_progress(self):
        return self._progress

    progress = Property(float, get_progress, notify=progressChanged)

    def get_running(self):
        return getattr(self, '_running', False)

    runningChanged = downloadStateChanged
    running = Property(bool, get_running, notify=downloadStateChanged)

    # ------------------------------------------------------------- sources
    def build_sources(self):
        self.srcs = C.build_sources(self.cfg)
        self._refresh_sources_model()

    def _refresh_sources_model(self):
        enabled = set(C.enabled_sources(self.cfg))
        items = []
        for n in C.ordered_sources(self.cfg):
            items.append({"name": n, "note": SOURCE_NOTES.get(n, ""), "enabled": n in enabled,
                          "status": "", "statusKind": "muted"})
        self.sources.setItems(items)
        self.sourcesChanged.emit()

    def get_sourcesHealth(self):
        out = []
        for it in self.sources._items:
            kind = "ok" if it["enabled"] else "muted"
            if it.get("statusKind") in ("ok", "bad", "warn"):
                kind = it["statusKind"]
            out.append({"name": it["name"], "color": self.get_palette().get(kind, "#888888")})
        return out

    sourcesHealth = Property("QVariantList", get_sourcesHealth, notify=sourcesChanged)

    def make_downloader(self, lang, log):
        provs, skipped = [], []
        for n in C.enabled_sources(self.cfg):
            s = self.srcs[n]
            if hasattr(s, "configured") and not s.configured():
                skipped.append(n)
            else:
                provs.append(C.AutoAdapter(s, lang))
        dl = C.Downloader(provs, lang, log, opts=dict(self.clean_opts_state), sevenzip=self._sevenzip(),
                          weak_save=self.cfg.get("weak_save", False), use_hash=self.cfg.get("use_hash", True))
        return dl, skipped

    def _sevenzip(self):
        if not self.cfg.get("sevenzip_on", True):
            return None
        return C.find_7z(self.cfg.get("sevenzip_path", ""))

    # --------------------------------------------------------------- auto
    def get_folder(self):
        return self._folder

    folder = Property(str, get_folder, notify=statusChanged)

    @Slot(result=str)
    def browseFolder(self):
        d = QFileDialog.getExistingDirectory(None, APP_NAME, self._folder or None)
        return d or ""

    @Slot(result=str)
    def browseSubtitleFile(self):
        p, _ = QFileDialog.getOpenFileName(None, APP_NAME, "",
                                           "Subtitles (*.srt *.ass *.ssa *.vtt);;All files (*.*)")
        return p or ""

    @Slot(result=str)
    def browseAnyFile(self):
        p, _ = QFileDialog.getOpenFileName(None, APP_NAME, "")
        return p or ""

    @Slot(str)
    def setFolder(self, path):
        self._folder = path
        if os.path.isdir(path):
            self.cfg["last_folder"] = path
            C.save_config(self.cfg)
        self.scan()

    @Slot("QVariant")
    def setPaths(self, urls):
        paths = []
        for u in urls:
            p = QUrl(u).toLocalFile() if str(u).startswith("file:") else str(u)
            if os.path.exists(p):
                paths.append(p)
        if paths:
            self._load_videos(paths)

    @Slot()
    def scan(self):
        folder = self._folder.strip()
        if os.path.isdir(folder):
            self._load_videos([folder])
        else:
            self._set_status(T("Pick a folder with videos first."))

    def _load_videos(self, paths):
        sub = self.cfg.get("include_subfolders", True)
        vids = C.videos_from_paths(paths, sub)
        self.base = paths[0] if len(paths) == 1 and os.path.isdir(paths[0]) else None
        self.base_folder = self.base
        if len(paths) == 1 and os.path.isdir(paths[0]):
            self.cfg["last_folder"] = paths[0]
            C.save_config(self.cfg)
        self.videos = [VideoInfo(p) for p in vids]
        suffix = LANGS[self.cfg.get("language", "English")]["suffix"]
        items = []
        for i, info in enumerate(self.videos):
            shown = os.path.relpath(info.path, self.base) if self.base else os.path.basename(info.path)
            has = C.existing_sub(info.path, suffix)
            items.append({"path": info.path, "title": info.label(), "file": shown,
                          "status": T("has subtitle") if has else T("waiting"),
                          "tag": "ok" if has else "", "sel": False,
                          "pc": POSTER_COLORS[i % len(POSTER_COLORS)],
                          "mtype": T("Series") if info.is_episode else T("Movie")})
        self.movies.setItems(items)
        self._set_status(f"{len(self.videos)} video(s)")
        self.logLine.emit(f"Found {len(self.videos)} video file(s)")

    def _row_of(self, path):
        for i, it in enumerate(self.movies._items):
            if it["path"] == path:
                return i
        return None

    def _on_movie_status(self, path, text, tag):
        i = self._row_of(path)
        if i is not None:
            self.movies.updateRow(i, status=text, tag=tag)

    @Slot(str, bool)
    def setOption(self, key, on):
        if key in DEFAULT_CLEAN:
            self.clean_opts_state[key] = bool(on)
            self.cfg["clean"] = dict(self.clean_opts_state)
        elif key in ("include_subfolders", "watch_folder"):
            self.cfg[key] = bool(on)
        elif key == "overwrite":
            self.cfg["overwrite"] = bool(on)
        C.save_config(self.cfg)

    @Slot(str, result=bool)
    def option(self, key):
        if key in DEFAULT_CLEAN:
            return bool(self.clean_opts_state.get(key))
        return bool(self.cfg.get(key, key == "include_subfolders"))

    @Slot(result="QVariantList")
    def languages(self):
        return list(LANGS)

    @Slot(str)
    def setLanguage(self, lang):
        self.cfg["language"] = lang
        C.save_config(self.cfg)

    @Slot(result=str)
    def language(self):
        return self.cfg.get("language", "English")

    @Slot()
    def startDownload(self):
        if self.running:
            return
        lang = self.cfg.get("language", "English")
        langs = [lang]
        second = self.cfg.get("language2", "")
        if second and second in LANGS and second != lang:
            langs.append(second)
        dls, skipped = [], []
        for lg in langs:
            dl, sk = self.make_downloader(lg, lambda m: self.logLine.emit(str(m)))
            skipped = sk
            if dl.providers:
                dls.append(dl)
        if skipped:
            self.logLine.emit("Skipped (not set up in Settings > Sources): " + ", ".join(skipped))
        if not dls:
            self._emit_toast(T("No usable source. Open Settings > Sources, enable a source and add its key."))
            return
        if not self.videos:
            self.scan()
        todo = list(self.videos)
        if not todo:
            return
        C.save_config(self.cfg)
        self.dls = dls
        self._running = True
        self.stop_flag.clear()
        self.downloadStateChanged.emit()
        self._set_progress(0.0)
        threading.Thread(target=self._run_download, args=(dls, todo, self.cfg.get("overwrite", False)),
                         daemon=True).start()

    @Slot()
    def stopDownload(self):
        self.stop_flag.set()

    def _run_download(self, dls, todo, overwrite):
        ok = 0
        rank = {"error": 4, "review": 3, "none": 2, "ok": 1, "skip": 0}
        for i, info in enumerate(todo, 1):
            if self.stop_flag.is_set():
                break
            self.movieStatusChanged.emit(info.path, T("searching..."), "")
            results = []
            for dl in dls:
                try:
                    results.append((dl.suffix,) + dl.fetch_for(info, overwrite))
                except Exception as e:  # noqa: BLE001
                    dlog(f"auto error: {e!r}")
                    results.append((dl.suffix, "error", "error: " + friendly_error(e)))
            worst = max(results, key=lambda r: rank[r[1]])[1]
            text = results[0][2] if len(results) == 1 else "  |  ".join(f"{s}: {m}" for s, _c, m in results)
            tag = {"ok": "ok", "skip": "", "review": "review"}.get(worst, "bad")
            ok += sum(r[1] == "ok" for r in results)
            if worst in ("none", "error", "review"):
                self.attempted[info.path] = time.time()
            self.movieStatusChanged.emit(info.path, text, tag)
            self.logLine.emit(f"{info.label()}: {text}")
            frac = i / len(todo)
            QTimer.singleShot(0, self, lambda f=frac: self._set_progress(f))
        self._running = False
        self.logLine.emit(f"Finished: {ok} subtitle(s) downloaded for {len(todo)} video(s).")
        QTimer.singleShot(0, self, lambda: (self._set_progress(-1.0), self.downloadStateChanged.emit()))

    def _watch_tick(self):
        try:
            if not (self.cfg.get("watch_folder") and not self.running):
                return
            folder = self._folder.strip()
            if not os.path.isdir(folder):
                return
            known = {v.path for v in self.videos}
            sub = self.cfg.get("include_subfolders", True)
            fresh = [VideoInfo(p) for p in C.find_videos(folder, sub) if p not in known]
            suffix = LANGS[self.cfg.get("language", "English")]["suffix"]
            if fresh:
                self._load_videos([folder])
            now = time.time()
            todo = [v for v in self.videos if not C.existing_sub(v.path, suffix)
                    and now - self.attempted.get(v.path, 0) > 6 * 3600
                    and now - os.path.getmtime(v.path) > 60]
            if todo:
                self.logLine.emit(f"Watch: {len(todo)} new video(s) without subtitles")
                self.startDownload()
        except Exception as e:  # noqa: BLE001
            dlog(f"watch error: {e!r}")

    # ------------------------------------------------- details / candidates
    def get_details(self):
        return self._details

    details = Property("QVariantMap", get_details, notify=detailsChanged)

    @Slot(int)
    def selectMovie(self, row):
        it = self.movies.itemAt(row)
        for i in range(len(self.movies._items)):
            if self.movies._items[i].get("sel"):
                self.movies.updateRow(i, sel=False)
        if it:
            self.movies.updateRow(row, sel=True)
        info = next((v for v in self.videos if v.path == (it or {}).get("path")), None)
        if not info:
            return
        self.cur_video = info
        self._details = {"title": info.label(), "meta": str(info.year or ""), "fname": os.path.basename(info.path),
                         "chip": "", "chipKind": "ok", "poster": ""}
        self.candidates.setItems([])
        self.detailsChanged.emit()
        lang = self.cfg.get("language", "English")
        dl, _ = self.make_downloader(lang, lambda m: None)
        self._cand_dl = dl if dl.providers else None
        key = info.title

        def details_work():
            d = self.details_cache.get(key)
            if d is None:
                d = C.imdb_details(info.title, info.year) or {}
                self.details_cache[key] = d
            return d

        def details_done(d, err):
            if err or d is None or self.cur_video is not info:
                return
            if d.get("title"):
                year = d.get("year") or ""
                self._details["title"] = f"{d['title']} ({year})" if year else d["title"]
            meta = " · ".join(x for x in (d.get("type", ""), (d.get("cast") or "")[:48]) if x)
            if meta:
                self._details["meta"] = meta
            if d.get("poster"):
                self._details["poster"] = d["poster"]
            self.detailsChanged.emit()
        self._bg(details_work, details_done)

        if self._cand_dl:
            self._set_status(T("Loading subtitle candidates..."))

            def cand_work():
                return self._cand_dl.list_candidates(info)

            def cand_done(res, err):
                if self.cur_video is not info:
                    return
                if err:
                    self._set_status("Error: " + friendly_error(err))
                    return
                items, errs = res
                rows = []
                for i, it in enumerate(items):
                    c = it["cand"]
                    okc = c.get("hash") or c["quality"] >= C.WEAK
                    rows.append({"idx": i, "release": c.get("release_name", ""),
                                 "why": c.get("reason", ""),
                                 "badge": "Best match" if c.get("hash") else ("Good" if okc else "Check"),
                                 "badgeKind": "ok" if okc else "warn",
                                 "whyKind": "ok" if okc else "warn"})
                self._cand_items = {str(i): it for i, it in enumerate(items)}
                self.candidates.setItems(rows)
                msg = f"{len(items)} candidate(s)"
                if errs:
                    msg += "   |   " + "; ".join(errs)
                self._set_status(msg)
                if items:
                    c = items[0]["cand"]
                    okc = c.get("hash") or c["quality"] >= C.WEAK
                    self._details["chip"] = (("\u2713 " if okc else "\u26a0 ") +
                                             ("Exact match · file hash" if c.get("hash")
                                              else ("Good match" if okc else "Weak match")))
                    self._details["chipKind"] = "ok" if okc else "warn"
                    self.detailsChanged.emit()
            self._bg(cand_work, cand_done)

    @Slot(int)
    def downloadCandidate(self, row):
        it = self.candidates.itemAt(row)
        info, dl = self.cur_video, getattr(self, "_cand_dl", None)
        if not it or not info or not dl:
            return
        cand = self._cand_items.get(str(it["idx"]))
        self._set_status(T("Saving..."))

        def work():
            return dl.save_item(info, cand)

        def done(path, err):
            if err:
                self._set_status("Error: " + friendly_error(err))
                return
            self._set_status("")
            self.movieStatusChanged.emit(info.path, f"OK (manual)  ->  {os.path.basename(path)}", "ok")
            self._emit_toast(T("Subtitle saved."))
        self._bg(work, done)

    @Slot(int)
    def previewCandidate(self, row):
        it = self.candidates.itemAt(row)
        info, dl = self.cur_video, getattr(self, "_cand_dl", None)
        if not it or not info or not dl:
            return
        cand = self._cand_items.get(str(it["idx"]))
        self._set_status(T("Loading preview..."))
        self._bg(lambda: dl.preview_item(info, cand),
                 lambda text, err: self._set_status("Error: " + friendly_error(err)) if err
                 else (self._set_status(""), self.previewReady.emit(T("Preview"), text)))

    # --------------------------------------------------------------- search
    @Slot(result="QVariantList")
    def sourceNames(self):
        return ["All sources"] + list(C.enabled_sources(self.cfg))

    @Slot(str, str)
    def search(self, text, source):
        text = text.strip()
        if not text:
            self._set_status(T("Type a movie / series name or an IMDb id (tt1234567)"))
            return
        names = C.enabled_sources(self.cfg) if source in ("All sources", "") else [source]
        self._set_status(T("Searching..."))
        self.results.setItems([])
        self.subs.setItems([])

        def work():
            out = []
            for n in names:
                try:
                    for it in self.srcs[n].search(text):
                        out.append(it)
                except Exception as e:  # noqa: BLE001
                    dlog(f"search {n}: {e!r}")
            return out[:24]

        def done(res, err):
            if err:
                self._set_status("Error: " + friendly_error(err))
                return
            self.search_items = {str(i): it for i, it in enumerate(res)}
            rows = [{"idx": i, "title": it.get("title", ""), "source": it.get("source", ""),
                     "year": str(it.get("year") or ""), "pc": POSTER_COLORS[i % len(POSTER_COLORS)]}
                    for i, it in enumerate(res)]
            self.results.setItems(rows)
            self._set_status(f"{len(rows)} result(s)" if rows else T("No results. Try another name."))
        self._bg(work, done)

    @Slot(int)
    def selectResult(self, row):
        it = self.results.itemAt(row)
        if not it:
            return
        item = self.search_items.get(str(it["idx"]))
        if not item:
            return
        self.cur_result = item
        lang = self.cfg.get("language", "English")
        src = self.srcs[item["source"]]
        self._set_status(f"Loading {lang} subtitles...")
        self.subs.setItems([])
        self._bg(lambda: src.subs(item, lang),
                 lambda r, e, it=item: self._subs_loaded(it, r, e))

        def details_work():
            d = self.details_cache.get(item["title"])
            if d is None:
                d = C.imdb_details(item["title"], item.get("year")) or {}
                self.details_cache[item["title"]] = d
            return d

        def details_done(d, err):
            if err or d is None or self.cur_result is not item:
                return
            self._details = {"title": d.get("title") or item.get("title", ""),
                             "meta": " · ".join(x for x in (str(d.get("year") or ""), d.get("type", ""),
                                                            (d.get("cast") or "")[:48]) if x),
                             "fname": "", "chip": "", "chipKind": "ok", "poster": d.get("poster") or ""}
            self.detailsChanged.emit()
        self._bg(details_work, details_done)

    def _subs_loaded(self, item, res, err):
        if self.cur_result is not item:
            return
        if err:
            self._set_status("Error: " + friendly_error(err))
            return
        self.sub_items = {str(i): s for i, s in enumerate(res or [])}
        rows = []
        for i, s in enumerate(res or []):
            rows.append({"idx": i, "release": s.get("release", ""), "lang": s.get("lang", ""),
                         "author": s.get("author", ""), "why": s.get("reason", "") or "",
                         "badge": "Good" if i == 0 else "", "badgeKind": "ok", "whyKind": "muted"})
        self.subs.setItems(rows)
        self._set_status(f"{len(rows)} subtitle(s)" if rows else T("No subtitles listed for this language."))

    def _picked_sub(self, row):
        it = self.subs.itemAt(row)
        return self.sub_items.get(str(it["idx"])) if it else None

    @Slot(int)
    def downloadSub(self, row):
        s = self._picked_sub(row)
        if not s or not self.cur_result:
            self._set_status(T("Select a subtitle first."))
            return
        dest = self.cfg.get("dest") or os.path.join(os.path.expanduser("~"), "Downloads")
        if self.cfg.get("ask_dest"):
            d = QFileDialog.getExistingDirectory(None, T("Save subtitles to..."))
            if not d:
                return
            dest = d
        src = self.srcs[self.cur_result["source"]]
        lang, opts = self.cfg.get("language", "English"), dict(self.clean_opts_state)
        extract, z = self.cfg.get("extract", True), self._sevenzip()
        self._set_status(T("Downloading..."))

        def work():
            name, data = src.fetch(s)
            return C.save_blob(data, name, dest, lang, opts, extract, z)

        def done(r, err):
            if err:
                self._set_status("Error: " + friendly_error(err))
            else:
                self._set_status("")
                self._emit_toast(f"{r}  ->  {dest}")
        self._bg(work, done)

    @Slot(int)
    def previewSub(self, row):
        s = self._picked_sub(row)
        if not s or not self.cur_result:
            self._set_status(T("Select a subtitle to preview."))
            return
        src = self.srcs[self.cur_result["source"]]
        lang, opts, z = self.cfg.get("language", "English"), dict(self.clean_opts_state), self._sevenzip()
        self._set_status(T("Loading preview..."))

        def work():
            name, data = src.fetch(s)
            return C.preview_text(data, name, lang, opts, z)

        def done(text, err):
            if err:
                self._set_status("Error: " + friendly_error(err))
            else:
                self._set_status("")
                self.previewReady.emit(T("Preview"), text)
        self._bg(work, done)

    @Slot()
    def openResultInBrowser(self):
        if self.cur_result:
            webbrowser.open(self.cur_result.get("url")
                            or f"https://www.google.com/search?q={self.cur_result['title']}+subtitles")

    # ----------------------------------------------------------- tools page
    @Slot(str, int, str, str, bool)
    def toolsApply(self, path, shift, f_from, f_to, replace):
        if not path or not os.path.isfile(path):
            self._emit_toast(T("Pick a subtitle file first."))
            return
        try:
            ff = float(f_from) if f_from else None
            ft = float(f_to) if f_to else None
        except ValueError:
            self._emit_toast("Frame rates must be numbers.")
            return
        lang, opts = self.cfg.get("language", "English"), dict(self.clean_opts_state)
        self._bg(lambda: C.transform_file(path, shift, ff, ft, lang, opts, replace),
                 lambda r, e: self._emit_toast(("Error: " + friendly_error(e)) if e else r[1]))

    @Slot(str)
    def planRenames(self, folder):
        if not folder or not os.path.isdir(folder):
            self._emit_toast(T("Pick a folder with videos first."))
            return
        plan = C.plan_renames([folder])
        if not plan:
            self._emit_toast(T("Nothing to rename - all names already look clean."))
            return
        text = "\n".join(f"{os.path.basename(o)}\n   ->  {os.path.basename(n)}" for o, n in plan)
        self.renamePreviewReady.emit(text, len(plan))
        self._rename_plan = plan

    @Slot()
    def applyRenames(self):
        plan = getattr(self, "_rename_plan", None)
        if not plan:
            self._emit_toast(T("Nothing to rename."))
            return
        done = C.apply_renames(plan)
        self._rename_plan = None
        self._emit_toast(T("Renamed") + f" {len(done)} " + T("file(s). Use Undo to restore."))

    @Slot()
    def undoRenames(self):
        restored = C.undo_last_rename()
        self._emit_toast((T("Restored") + f" {len(restored)} " + T("file(s)."))
                         if restored else T("Nothing to undo."))

    # ------------------------------------------------------------- settings
    @Slot(result="QVariantMap")
    def settings(self):
        c = self.cfg
        order = C.ordered_sources(c)
        enabled = set(C.enabled_sources(c))
        defaults = {n: v[0] for n, v in C.SITES.items()}
        return {
            "ui_lang": c.get("ui_lang", "en"), "theme": c.get("theme", "system"),
            "language": c.get("language", "English"), "language2": c.get("language2") or "",
            "dest": c.get("dest") or os.path.join(os.path.expanduser("~"), "Downloads"),
            "ask_dest": c.get("ask_dest", False), "extract": c.get("extract", True),
            "check_updates": c.get("check_updates", True),
            "use_hash": c.get("use_hash", True), "weak_save": c.get("weak_save", False),
            "sevenzip_on": c.get("sevenzip_on", True), "sevenzip_path": c.get("sevenzip_path", ""),
            "sevenzip_found": bool(self._sevenzip()),
            "clean": dict(self.clean_opts_state),
            "order": order, "enabled": {n: n in enabled for n in order},
            "sites": {n: c.get("sites", {}).get(n) or d for n, d in defaults.items()},
            "site_defaults": defaults,
            "subsource_key": C.get_secret(c, "subsource_key"), "os_key": C.get_secret(c, "os_key"),
            "os_user": c.get("os_user", ""), "os_pass": C.get_secret(c, "os_pass"),
            "portable": C.is_portable(), "data_dir": C.data_dir(),
            "secrets_store": "system keyring" if C.secrets_backend() == "keyring"
                             else "config.json (plain text)",
        }

    @Slot("QVariantMap")
    def saveSettings(self, m):
        c = self.cfg
        for k in ("language", "language2", "dest", "ask_dest", "extract", "check_updates",
                  "use_hash", "weak_save", "sevenzip_on", "sevenzip_path", "ui_lang", "theme"):
            if k in m:
                c[k] = m[k]
        if "clean" in m:
            self.clean_opts_state = dict(DEFAULT_CLEAN, **{k: bool(v) for k, v in m["clean"].items()})
            c["clean"] = dict(self.clean_opts_state)
        if "enabled" in m:
            c["enabled"] = dict(m["enabled"])
        if "order" in m:
            c["order"] = list(m["order"])
        if "sites" in m:
            defaults = {n: v[0] for n, v in C.SITES.items()}
            c["sites"] = {n: v for n, v in m["sites"].items() if v and v != defaults.get(n)}
        if "os_user" in m:
            c["os_user"] = str(m["os_user"]).strip()
        for name in ("subsource_key", "os_key", "os_pass"):
            if name in m:
                C.set_secret(c, name, str(m[name]))
        C.save_config(c)
        self.build_sources()
        self._palette_version += 1
        self._regen_icons()
        self.paletteChanged.emit()
        self._emit_toast(T("Saved."))

    @Slot(str)
    def testSource(self, name):
        self.sources.updateRow(self._source_row(name), status="testing...", statusKind="muted")
        self.sourcesChanged.emit()

        def done(res, err):
            ok, msg = (False, friendly_error(err)) if err else res
            row = self._source_row(name)
            if row is not None:
                self.sources.updateRow(row, status=("\u2713 " if ok else "\u2717 ") + msg,
                                       statusKind="ok" if ok else "bad")
            self.sourcesChanged.emit()
        self._bg(lambda: C.test_source(C.build_sources(self.cfg)[name]), done)

    def _source_row(self, name):
        for i, it in enumerate(self.sources._items):
            if it["name"] == name:
                return i
        return None

    @Slot()
    def updateSources(self):
        self._set_status(T("Checking sources..."))
        for n in C.enabled_sources(self.cfg):
            self.testSource(n)

    @Slot()
    def checkUpdates(self):
        def done(res, err):
            if err:
                self._emit_toast("Could not check: " + friendly_error(err))
            elif res:
                self._emit_toast(f"Version {res[0]} is available: {res[1]}")
                webbrowser.open(res[1])
            else:
                self._emit_toast("You are up to date.")
        self._bg(C.check_update, done)

    @Slot(str)
    def openDataPath(self, which):
        p = os.path.join(C.data_dir(), "debug.log") if which == "log" else C.data_dir()
        if which == "log" and not os.path.exists(p):
            open(p, "a").close()
        try:
            os.startfile(p)  # Windows
        except AttributeError:
            webbrowser.open("file://" + p)

    @Slot(str)
    def openUrl(self, url):
        webbrowser.open(url)

    @Slot(str)
    def openFolder(self, path):
        if path and os.path.isdir(path):
            try:
                os.startfile(path)  # Windows
            except AttributeError:
                webbrowser.open("file://" + path)

    # --------------------------------------------------------- splitters
    @Slot(str, result="QVariantList")
    def splitter(self, key):
        return self.cfg.get("splitters_qml", {}).get(key) or []

    @Slot(str, "QVariantList")
    def saveSplitter(self, key, sizes):
        d = dict(self.cfg.get("splitters_qml", {}))
        d[key] = [int(x) for x in sizes]
        self.cfg["splitters_qml"] = d
        C.save_config(self.cfg)

    @Slot(result="QVariantMap")
    def appInfo(self):
        return {"name": APP_NAME, "version": VERSION}


def _qml_dir():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "qml")


def main(cfg=None):
    cfg = cfg or C.load_config()
    UI["lang"] = cfg.get("ui_lang", "en")
    UI["rtl"] = UI["lang"] == "ar"
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    font_path = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
                             "assets", "Inter-Variable.ttf")
    if os.path.isfile(font_path):
        QFontDatabase.addApplicationFont(font_path)
    import base64
    if LOGO_PNG_B64:
        from PySide6.QtGui import QPixmap
        pm = QPixmap()
        pm.loadFromData(base64.b64decode(LOGO_PNG_B64))
        if not pm.isNull():
            app.setWindowIcon(QIcon(pm))
    bridge = Bridge(cfg)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.rootContext().setContextProperty("moviesModel", bridge.movies)
    engine.rootContext().setContextProperty("candidatesModel", bridge.candidates)
    engine.rootContext().setContextProperty("resultsModel", bridge.results)
    engine.rootContext().setContextProperty("subsModel", bridge.subs)
    engine.rootContext().setContextProperty("sourcesModel", bridge.sources)
    engine.addImportPath(_qml_dir())
    engine.load(QUrl.fromLocalFile(os.path.join(_qml_dir(), "Main.qml")))
    if not engine.rootObjects():
        dlog("QML failed to load")
        return 2
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
