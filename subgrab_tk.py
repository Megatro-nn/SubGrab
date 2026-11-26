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
SubGrab - the Tk interface (all logic lives in subgrab_core.py).

Pages: Auto Folder, Search, Subtitle Tools, Settings.
"""
import base64
import io
import os
import queue
import subprocess
import sys
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import subgrab_core as C
from subgrab_core import (APP_NAME, DEFAULT_CLEAN, GITHUB_REPO, KEY_SOURCES, LANGS, SOURCE_ORDER, VERSION,
                          VideoInfo, dlog, friendly_error)

try:  # optional: posters in the Search page
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:  # pragma: no cover
    HAVE_PIL = False

try:
    from subgrab_assets import LOGO_PNG_B64
except Exception:  # pragma: no cover
    LOGO_PNG_B64 = ""

from subgrab_i18n import UI, AR, T  # noqa: F401


def side(start=True):
    """pack side for 'start' (True) or 'end' (False) of a row; mirrored in Arabic."""
    return ("right" if start else "left") if UI["rtl"] else ("left" if start else "right")


def anchor():
    return "e" if UI["rtl"] else "w"


# --------------------------------------------------------------------- theme
LIGHT = dict(bg="#f3f3f3", panel="#fafafa", fg="#1a1a1a", muted="#555555", accent="#0067c0", hover="#e9e9e9",
             select="#e1e1e1", entry="#ffffff", border="#c9c9c9", tree="#ffffff", head="#f0f0f0",
             ok="#e6f4ea", warn="#fff4ce", bad="#fde7e9")
DARK = dict(bg="#202020", panel="#272727", fg="#f0f0f0", muted="#b0b0b0", accent="#4cc2ff", hover="#323232",
            select="#3a3a3a", entry="#1f1f1f", border="#444444", tree="#1f1f1f", head="#2d2d2d",
            ok="#1e3a26", warn="#4a3d10", bad="#4a2024")
P = dict(LIGHT)
FONT = ("Segoe UI", 10)


def system_is_dark():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except Exception:
        return False


def configure_ui(cfg):
    UI["lang"] = cfg.get("ui_lang", "en")
    UI["rtl"] = UI["lang"] == "ar"
    theme = cfg.get("theme", "system")
    dark = theme == "dark" or (theme == "system" and system_is_dark())
    P.clear()
    P.update(DARK if dark else LIGHT)
    P["dark"] = dark


def apply_style(root):
    st = ttk.Style(root)
    names = st.theme_names()
    try:
        st.theme_use("clam" if (P.get("dark") or "vista" not in names) else "vista")
    except Exception:
        pass
    if P.get("dark") or "vista" not in names:
        st.configure(".", background=P["panel"], foreground=P["fg"], fieldbackground=P["entry"],
                     bordercolor=P["border"], lightcolor=P["panel"], darkcolor=P["panel"], troughcolor=P["bg"])
        st.configure("TButton", background=P["head"], foreground=P["fg"], bordercolor=P["border"])
        st.map("TButton", background=[("active", P["hover"]), ("pressed", P["select"])])
        st.configure("TEntry", fieldbackground=P["entry"], foreground=P["fg"], insertcolor=P["fg"])
        st.configure("TCombobox", fieldbackground=P["entry"], background=P["head"], foreground=P["fg"],
                     arrowcolor=P["fg"], selectbackground=P["entry"], selectforeground=P["fg"])
        st.map("TCombobox", fieldbackground=[("readonly", P["entry"])], foreground=[("readonly", P["fg"])])
        st.configure("TNotebook", background=P["panel"], bordercolor=P["border"])
        st.configure("TNotebook.Tab", background=P["head"], foreground=P["fg"], padding=(14, 6))
        st.map("TNotebook.Tab", background=[("selected", P["panel"])])
        st.configure("TCheckbutton", background=P["panel"], foreground=P["fg"])
        st.map("TCheckbutton", background=[("active", P["panel"])])
        st.configure("TProgressbar", background=P["accent"], troughcolor=P["head"])
        st.configure("TSeparator", background=P["border"])
        st.configure("Vertical.TScrollbar", background=P["head"], troughcolor=P["bg"], arrowcolor=P["fg"])
    st.configure("Treeview", rowheight=30, font=FONT, background=P["tree"], fieldbackground=P["tree"], foreground=P["fg"])
    st.map("Treeview", background=[("selected", P["accent"])],
           foreground=[("selected", "#ffffff" if not P.get("dark") else "#000000")])
    st.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background=P["head"], foreground=P["fg"])
    st.configure("TLabel", background=P["panel"], foreground=P["fg"], font=FONT)
    st.configure("TCheckbutton", font=FONT)
    st.configure("TButton", font=FONT, padding=(10, 5))
    root.option_add("*TCombobox*Listbox.background", P["entry"])
    root.option_add("*TCombobox*Listbox.foreground", P["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", P["accent"])


# ------------------------------------------------------------------- widgets
class NavItem(tk.Frame):
    def __init__(self, parent, icon, text, command):
        super().__init__(parent, bg=P["bg"], height=46)
        self.pack_propagate(False)
        self.active = False
        self.bar = tk.Frame(self, width=3, bg=P["bg"])
        self.bar.pack(side=side(True), fill="y", pady=11, padx=(4, 4))
        self.lbl = tk.Label(self, text=f"{icon}   {text}", bg=P["bg"], fg=P["fg"], font=("Segoe UI", 11),
                            anchor=anchor(), padx=14)
        self.lbl.pack(side=side(True), fill="both", expand=True)
        for w in (self, self.lbl, self.bar):
            w.bind("<Button-1>", lambda e: command())
            w.bind("<Enter>", lambda e: self.paint(True))
            w.bind("<Leave>", lambda e: self.paint(False))

    def paint(self, hover=False):
        col = P["select"] if self.active else (P["hover"] if hover else P["bg"])
        for w in (self, self.lbl):
            w.configure(bg=col)
        self.bar.configure(bg=P["accent"] if self.active else col)

    def set_active(self, on):
        self.active = on
        self.paint(False)


class SearchBox(tk.Frame):
    """Bordered entry with a magnifier and placeholder text."""

    def __init__(self, parent, command, placeholder=None):
        super().__init__(parent, bg=P["entry"], highlightthickness=1, highlightbackground=P["border"])
        self.placeholder = placeholder or T("Search Movie\\Series by Name or IMDB id")
        self.command, self.has_text = command, False
        self.entry = tk.Entry(self, relief="flat", font=("Segoe UI", 12), fg=P["muted"], bg=P["entry"],
                              insertbackground=P["fg"], justify="right" if UI["rtl"] else "left")
        self.entry.pack(side=side(True), fill="x", expand=True, padx=10, ipady=7)
        self.btn = tk.Canvas(self, width=40, height=30, bg=P["entry"], highlightthickness=0, cursor="hand2")
        self.btn.create_oval(12, 7, 24, 19, outline=P["muted"], width=2)
        self.btn.create_line(23, 18, 29, 24, fill=P["muted"], width=2)
        self.btn.pack(side=side(False))
        self.btn.bind("<Button-1>", lambda e: self.command())
        self.entry.bind("<Return>", lambda e: self.command())
        self.entry.bind("<FocusIn>", self._in)
        self.entry.bind("<FocusOut>", self._out)
        self._placeholder()

    def _placeholder(self):
        self.entry.delete(0, "end")
        self.entry.insert(0, self.placeholder)
        self.entry.configure(fg=P["muted"])
        self.has_text = False

    def _in(self, _e):
        if not self.has_text:
            self.entry.delete(0, "end")
            self.entry.configure(fg=P["fg"])
            self.has_text = True
        self.configure(highlightbackground=P["accent"])

    def _out(self, _e):
        self.configure(highlightbackground=P["border"])
        if not self.entry.get().strip():
            self._placeholder()

    def get(self):
        return self.entry.get().strip() if self.has_text else ""

    def set(self, text):
        self.entry.delete(0, "end")
        self.entry.insert(0, text)
        self.entry.configure(fg=P["fg"])
        self.has_text = True


def make_tree(parent, columns, headings, widths, height=8):
    frame = tk.Frame(parent, bg=P["panel"])
    tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended", height=height)
    for c, h, w in zip(columns, headings, widths):
        tree.heading(c, text=h, anchor=anchor())
        tree.column(c, width=w, anchor=anchor(), stretch=(w >= 250))
    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    sb.pack(side=side(False), fill="y")
    tree.pack(side=side(True), fill="both", expand=True)
    tree.tag_configure("ok", background=P["ok"])
    tree.tag_configure("review", background=P["warn"])
    tree.tag_configure("bad", background=P["bad"])
    return frame, tree


def options_row(parent, app, bom=True):
    """The subtitle-clean-up checkboxes shared by Auto Folder, Search and Tools."""
    row = tk.Frame(parent, bg=P["panel"])
    ttk.Label(row, text=T("Subtitle options:")).pack(side=side(True))
    items = [("utf8", "Convert to UTF-8"), ("to_srt", "Convert to SRT"), ("ads", "Remove ads / watermarks"),
             ("hi", "Remove hearing-impaired tags")]
    if bom:
        items.append(("bom", "Add BOM (older TVs/players)"))
    for key, text in items:
        ttk.Checkbutton(row, text=T(text), variable=app.clean_vars[key], command=app.save_clean).pack(side=side(True), padx=6)
    return row


class TextDialog(tk.Toplevel):
    def __init__(self, app, title, text):
        super().__init__(app)
        self.title(title)
        self.geometry("760x520")
        self.configure(bg=P["panel"])
        fr = tk.Frame(self, bg=P["panel"])
        fr.pack(fill="both", expand=True, padx=10, pady=10)
        self.box = tk.Text(fr, wrap="word", font=("Consolas", 10), bg=P["entry"], fg=P["fg"],
                           insertbackground=P["fg"], relief="flat", highlightthickness=1, highlightbackground=P["border"])
        sb = ttk.Scrollbar(fr, orient="vertical", command=self.box.yview)
        self.box.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.box.pack(side="left", fill="both", expand=True)
        self.box.insert("1.0", text)
        self.box.configure(state="disabled")
        ttk.Button(self, text=T("Close"), command=self.destroy).pack(pady=(0, 10))


class PickDialog(tk.Toplevel):
    """Manual pick: every candidate from every source, with preview."""

    def __init__(self, page, info, downloader):
        super().__init__(page.app)
        self.page, self.info, self.dl, self.app = page, info, downloader, page.app
        self.title(f"{T('Pick manually...').rstrip('.')} - {info.label()}")
        self.geometry("980x540")
        self.configure(bg=P["panel"])
        ttk.Label(self, text=os.path.basename(info.path), font=("Segoe UI", 10, "bold")).pack(anchor=anchor(), padx=12, pady=(12, 4))
        fr, self.tree = make_tree(self, ("src", "rel", "score", "match", "why"),
                                  (T("Source"), T("Release"), T("Score"), T("Match"), T("Why")), (110, 480, 70, 90, 200), 14)
        fr.pack(fill="both", expand=True, padx=12, pady=6)
        self.tree.bind("<Double-1>", lambda e: self.use())
        bar = tk.Frame(self, bg=P["panel"])
        bar.pack(fill="x", padx=12, pady=(4, 12))
        ttk.Button(bar, text=T("Preview"), command=self.preview).pack(side=side(True))
        ttk.Button(bar, text=T("Use selected"), command=self.use).pack(side=side(True), padx=6)
        ttk.Button(bar, text=T("Close"), command=self.destroy).pack(side=side(True))
        self.status = ttk.Label(bar, text="Looking for candidates...")
        self.status.pack(side=side(True), padx=12)
        self.items = {}
        self.app.bg(lambda: self.dl.list_candidates(info), self.loaded)

    def alive(self):
        try:
            return bool(self.winfo_exists())
        except Exception:
            return False

    def loaded(self, res, err):
        if not self.alive():
            return
        if err:
            self.status.configure(text="Error: " + friendly_error(err))
            return
        items, errs = res
        for i, it in enumerate(items):
            c = it["cand"]
            self.items[str(i)] = it
            tag = "ok" if (c.get("hash") or c["quality"] >= C.WEAK) else "review"
            self.tree.insert("", "end", iid=str(i), tags=(tag,),
                             values=(it["prov"].name, c.get("release_name", ""), f"{c['quality']:.2f}",
                                     "file hash" if c.get("hash") else ("good" if tag == "ok" else "weak"),
                                     c.get("reason", "")))
        msg = f"{len(items)} candidate(s)"
        if errs:
            msg += "   |   " + "; ".join(errs)
        self.status.configure(text=msg)

    def current(self):
        sel = self.tree.selection()
        return self.items[sel[0]] if sel else None

    def preview(self):
        it = self.current()
        if not it:
            return
        self.status.configure(text="Loading preview...")
        self.app.bg(lambda: self.dl.preview_item(self.info, it),
                    lambda r, e: self._shown(r, e))

    def _shown(self, text, err):
        if not self.alive():
            return
        if err:
            self.status.configure(text="Error: " + friendly_error(err))
        else:
            self.status.configure(text="")
            TextDialog(self.app, T("Preview"), text)

    def use(self):
        it = self.current()
        if not it:
            return
        self.status.configure(text="Saving...")
        self.app.bg(lambda: self.dl.save_item(self.info, it), self._saved)

    def _saved(self, path, err):
        if not self.alive():
            return
        if err:
            self.status.configure(text="Error: " + friendly_error(err))
            return
        self.page.set_status(self.info.path, f"OK (manual)  ->  {os.path.basename(path)}", "ok")
        self.destroy()


class Page(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=P["panel"])
        self.app = app

    def on_show(self):
        pass


# ------------------------------------------------------------ Auto Folder page
class AutoPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.videos, self.base, self.running = [], None, False
        self.stop_flag = threading.Event()
        self.attempted = {}  # path -> time of last failed attempt (watch mode)
        self.dls = []

        top = tk.Frame(self, bg=P["panel"])
        top.pack(fill="x", padx=16, pady=(16, 4))
        top.columnconfigure(1, weight=1)
        arg = sys.argv[1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]) else None
        if getattr(sys, "frozen", False):
            start = arg or app.cfg.get("last_folder") or os.path.join(os.path.expanduser("~"), "Videos")
        else:
            start = arg or C.app_dir()
        self.folder_var = tk.StringVar(value=start)
        ttk.Label(top, text=T("Movie / series folder:")).grid(row=0, column=0, sticky=anchor())
        ttk.Entry(top, textvariable=self.folder_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(top, text=T("Browse..."), command=self.browse).grid(row=0, column=2)
        ttk.Button(top, text=T("Scan"), command=self.scan).grid(row=0, column=3, padx=(6, 0))

        opts = tk.Frame(self, bg=P["panel"])
        opts.pack(fill="x", padx=16, pady=4)
        ttk.Label(opts, text=T("Language:")).pack(side=side(True))
        self.lang_var = tk.StringVar(value=app.cfg.get("language", "English"))
        lc = ttk.Combobox(opts, textvariable=self.lang_var, values=list(LANGS), state="readonly", width=18)
        lc.pack(side=side(True), padx=6)
        lc.bind("<<ComboboxSelected>>", lambda e: self.refresh_status())
        self.sub_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text=T("Include subfolders"), variable=self.sub_var, command=self.scan).pack(side=side(True), padx=10)
        self.over_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text=T("Overwrite existing"), variable=self.over_var).pack(side=side(True))

        options_row(self, app).pack(fill="x", padx=16, pady=2)

        w = tk.Frame(self, bg=P["panel"])
        w.pack(fill="x", padx=16, pady=2)
        self.watch_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(w, text=T("Watch this folder for new videos"), variable=self.watch_var).pack(side=side(True))
        ttk.Label(w, text="   " + T("Drop folders or video files anywhere in this window"),
                  foreground=P["muted"]).pack(side=side(True))

        frame, self.tree = make_tree(self, ("file", "detected", "status"),
                                     (T("Video file"), T("Detected as"), T("Status")), (340, 210, 340), 12)
        frame.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree.bind("<Double-1>", lambda e: self.pick_manual())

        bar = tk.Frame(self, bg=P["panel"])
        bar.pack(fill="x", padx=16, pady=(0, 4))
        self.go_btn = ttk.Button(bar, text=T("Download subtitles"), command=self.start)
        self.go_btn.pack(side=side(True))
        self.stop_btn = ttk.Button(bar, text=T("Stop"), command=lambda: self.stop_flag.set(), state="disabled")
        self.stop_btn.pack(side=side(True), padx=6)
        ttk.Button(bar, text=T("Pick manually..."), command=self.pick_manual).pack(side=side(True))
        self.progress = ttk.Progressbar(bar, mode="determinate")
        self.progress.pack(side=side(True), fill="x", expand=True, padx=8)
        self.count = ttk.Label(bar, text="")
        self.count.pack(side=side(True))

        self.stats = ttk.Label(self, text="", foreground=P["muted"])
        self.stats.pack(fill="x", padx=16)
        self.log = tk.Text(self, height=5, state="disabled", font=("Consolas", 9), bg=P["entry"], fg=P["fg"],
                           relief="flat", highlightthickness=1, highlightbackground=P["border"])
        self.log.pack(fill="x", padx=16, pady=(4, 14))
        self.app.after(60000, self.watch_tick)

    # -- list handling
    def on_show(self):
        if not self.videos:
            self.scan()

    def write(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def browse(self):
        d = filedialog.askdirectory(initialdir=self.folder_var.get() or None)
        if d:
            self.folder_var.set(d)
            self.scan()

    def scan(self):
        folder = self.folder_var.get().strip()
        if os.path.isdir(folder):
            self.set_paths([folder])

    def set_paths(self, paths):
        """Used by Scan, the right-click menu argument and drag & drop."""
        paths = [p for p in paths if os.path.exists(p)]
        vids = C.videos_from_paths(paths, self.sub_var.get())
        self.base = paths[0] if len(paths) == 1 and os.path.isdir(paths[0]) else None
        if len(paths) == 1:
            self.folder_var.set(paths[0])
            if os.path.isdir(paths[0]):
                self.app.cfg["last_folder"] = paths[0]
        else:
            self.folder_var.set(f"{len(paths)} items")
        self.videos = [VideoInfo(p) for p in vids]
        self.tree.delete(*self.tree.get_children())
        for info in self.videos:
            shown = os.path.relpath(info.path, self.base) if self.base else os.path.basename(info.path)
            self.tree.insert("", "end", iid=info.path, values=(shown, info.label(), ""))
        self.refresh_status()
        self.count.configure(text=f"{len(self.videos)} video(s)")
        self.write(f"Found {len(self.videos)} video file(s)")

    def refresh_status(self):
        suffix = LANGS[self.lang_var.get()]["suffix"]
        for info in self.videos:
            if self.tree.exists(info.path):
                vals = list(self.tree.item(info.path, "values"))
                if vals[2] in ("", T("waiting"), T("has subtitle")):
                    vals[2] = T("has subtitle") if C.existing_sub(info.path, suffix) else T("waiting")
                    self.tree.item(info.path, values=vals)

    def set_status(self, path, text, tag=""):
        if self.tree.exists(path):
            vals = list(self.tree.item(path, "values"))
            vals[2] = text
            self.tree.item(path, values=vals, tags=(tag,) if tag else ())

    # -- downloading
    def start(self, todo=None, quiet=False):
        if self.running:
            return
        lang = self.lang_var.get()
        langs = [lang]
        second = self.app.cfg.get("language2", "")
        if second and second in LANGS and second != lang:
            langs.append(second)
        dls, skipped = [], []
        for lg in langs:
            dl, sk = self.app.make_downloader(lg, lambda m: self.app.ui(self.write, m))
            skipped = sk
            if dl.providers:
                dls.append(dl)
        if skipped:
            self.write("Skipped (not set up in Settings > Sources): " + ", ".join(skipped))
        if not dls:
            if not quiet:
                messagebox.showinfo(APP_NAME, "No usable source. Open Settings > Sources, enable a source and add its key if it needs one.")
            return
        if not self.videos:
            self.scan()
        if todo is None:
            sel = self.tree.selection()
            todo = [v for v in self.videos if (not sel or v.path in sel)]
        if not todo:
            return
        self.app.cfg["language"] = lang
        C.save_config(self.app.cfg)
        self.dls = dls
        self.running = True
        self.stop_flag.clear()
        self.go_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress.configure(maximum=len(todo), value=0)
        threading.Thread(target=self.run, args=(dls, todo, self.over_var.get()), daemon=True).start()

    def run(self, dls, todo, overwrite):
        ok = 0
        rank = {"error": 4, "review": 3, "none": 2, "ok": 1, "skip": 0}
        for i, info in enumerate(todo, 1):
            if self.stop_flag.is_set():
                break
            self.app.ui(self.set_status, info.path, T("searching..."), "")
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
            self.app.ui(self.set_status, info.path, text, tag)
            self.app.ui(self.write, f"{info.label()}: {text}")
            self.app.ui(lambda n=i: self.progress.configure(value=n))
            self.app.ui(self.show_stats)
            if all(r[2] == "error: no valid API key / login" for r in results):
                break
        self.app.ui(self.finished, ok, len(todo))

    def show_stats(self):
        txt = "  \u00b7  ".join(t for t in (d.stats_text() for d in self.dls) if t)
        self.stats.configure(text=(T("Sources:") + " " + txt) if txt else "")

    def finished(self, ok, total):
        self.running = False
        self.write(f"Finished: {ok} subtitle(s) downloaded for {total} video(s).")
        self.go_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    # -- manual pick
    def pick_manual(self):
        sel = self.tree.selection()
        if not sel:
            return
        info = next((v for v in self.videos if v.path == sel[0]), None)
        if not info:
            return
        dl, _skipped = self.app.make_downloader(self.lang_var.get(), lambda m: None)
        if not dl.providers:
            messagebox.showinfo(APP_NAME, "No usable source. Check Settings > Sources.")
            return
        PickDialog(self, info, dl)

    # -- watch mode
    def watch_tick(self):
        try:
            if self.watch_var.get() and not self.running:
                folder = self.folder_var.get().strip()
                if os.path.isdir(folder):
                    known = {v.path for v in self.videos}
                    fresh = [VideoInfo(p) for p in C.find_videos(folder, self.sub_var.get()) if p not in known]
                    for info in fresh:
                        self.videos.append(info)
                        self.tree.insert("", "end", iid=info.path, values=(os.path.relpath(info.path, folder), info.label(), T("waiting")))
                    suffix = LANGS[self.lang_var.get()]["suffix"]
                    now = time.time()
                    todo = [v for v in self.videos if not C.existing_sub(v.path, suffix)
                            and now - self.attempted.get(v.path, 0) > 6 * 3600
                            and now - os.path.getmtime(v.path) > 60]  # skip files still being copied
                    if todo:
                        self.write(f"Watch: {len(todo)} new video(s) without subtitles")
                        self.start(todo=todo, quiet=True)
        except Exception as e:
            dlog(f"watch error: {e!r}")
        self.app.after(60000, self.watch_tick)


# ----------------------------------------------------------------- Search page
class SearchPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.items, self.subs, self.cur, self.poster = {}, {}, None, None
        top = tk.Frame(self, bg=P["panel"])
        top.pack(fill="x", padx=16, pady=(16, 8))
        self.src_var = tk.StringVar(value=SOURCE_ORDER[0])
        ttk.Combobox(top, textvariable=self.src_var, values=SOURCE_ORDER, state="readonly", width=16,
                     font=("Segoe UI", 11)).pack(side=side(True), padx=10, ipady=4)
        self.box = SearchBox(top, self.run_search)
        self.box.pack(side=side(True), fill="x", expand=True)

        pw = tk.PanedWindow(self, orient="vertical", bg=P["panel"], sashwidth=6, sashrelief="flat")
        pw.pack(fill="both", expand=True, padx=16)
        upper = tk.Frame(pw, bg=P["panel"])
        f1, self.tree = make_tree(upper, ("title", "source"), (T("Results"), T("Source")), (480, 130), 7)
        self.card = tk.Frame(upper, bg=P["panel"], width=200)
        self.card.pack_propagate(False)
        self.card.pack(side=side(False), fill="y", padx=(8, 0))
        f1.pack(side=side(True), fill="both", expand=True)
        self.poster_lbl = tk.Label(self.card, bg=P["panel"])
        self.poster_lbl.pack(pady=(4, 6))
        self.info_lbl = tk.Label(self.card, bg=P["panel"], fg=P["fg"], font=("Segoe UI", 9), justify="left",
                                 wraplength=180, anchor="nw")
        self.info_lbl.pack(fill="x", padx=4)
        f2, self.subtree = make_tree(pw, ("release", "lang", "author"),
                                     (T("Subtitle / release"), T("Language"), T("Uploader")), (560, 110, 120), 9)
        pw.add(upper, minsize=150)
        pw.add(f2, minsize=140)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.pick_item())
        self.subtree.bind("<Double-1>", lambda e: self.download())

        options_row(self, app, bom=False).pack(fill="x", padx=16, pady=(8, 0))
        bar = tk.Frame(self, bg=P["panel"])
        bar.pack(fill="x", padx=16, pady=8)
        ttk.Label(bar, text=T("Language:")).pack(side=side(True))
        self.lang_var = tk.StringVar(value=app.cfg.get("language", "English"))
        lc = ttk.Combobox(bar, textvariable=self.lang_var, values=list(LANGS), state="readonly", width=20)
        lc.pack(side=side(True), padx=6)
        lc.bind("<<ComboboxSelected>>", lambda e: self.pick_item())
        ttk.Button(bar, text=T("Download"), command=self.download).pack(side=side(True), padx=(10, 4))
        ttk.Button(bar, text=T("Preview"), command=self.preview).pack(side=side(True), padx=4)
        ttk.Button(bar, text=T("Open in browser"), command=self.open_web).pack(side=side(True), padx=4)
        self.status = ttk.Label(bar, text="")
        self.status.pack(side=side(True), padx=12)

    def on_show(self):
        self.box.entry.focus_set()

    def say(self, text):
        self.status.configure(text=text)

    def run_search(self):
        q = self.box.get()
        if not q:
            self.say("Type a movie / series name or an IMDb id (tt1234567)")
            return
        src = self.app.source(self.src_var.get())
        self.say(f"Searching {src.name}...")
        self.tree.delete(*self.tree.get_children())
        self.subtree.delete(*self.subtree.get_children())
        self.app.bg(lambda: src.search(q), self.on_results)

    def on_results(self, res, err):
        self.tree.delete(*self.tree.get_children())
        self.subtree.delete(*self.subtree.get_children())
        self.items, self.cur = {}, None
        if err:
            self.say("Error: " + friendly_error(err))
            return
        for i, it in enumerate(res or []):
            self.items[str(i)] = it
            self.tree.insert("", "end", iid=str(i), values=(it["title"], it.get("source", "")))
        self.say(f"{len(self.items)} result(s). Click one to list its subtitles." if self.items
                 else "No results. Try the Test button in Settings > Sources to check this site.")

    def pick_item(self):
        sel = self.tree.selection()
        if not sel:
            return
        it = self.items[sel[0]]
        self.cur = it
        lang = self.lang_var.get()
        src = self.app.source(it["source"])
        self.say(f"Loading {lang} subtitles...")
        self.subtree.delete(*self.subtree.get_children())
        self.app.bg(lambda: src.subs(it, lang), lambda r, e, it=it: self.on_subs(it, r, e))
        self.app.bg(lambda: self.load_details(it), lambda r, e, it=it: self.on_details(it, r, e))

    def on_subs(self, it, res, err):
        if it is not self.cur:
            return
        self.subtree.delete(*self.subtree.get_children())
        self.subs = {}
        if err:
            self.say("Error: " + friendly_error(err))
            return
        for i, s in enumerate(res or []):
            self.subs[str(i)] = s
            self.subtree.insert("", "end", iid=str(i), values=(s.get("release", ""), s.get("lang", ""), s.get("author", "")))
        self.say(f"{len(self.subs)} subtitle(s). Double-click or press Download." if self.subs
                 else "No subtitles listed for this language.")

    # -- poster + details card (IMDb public data; poster needs Pillow)
    def load_details(self, it):
        d = self.app.details_cache.get(it["title"])
        if d is None:
            d = C.imdb_details(it["title"], it.get("year")) or {}
            img = None
            if d.get("poster") and HAVE_PIL:
                try:
                    img = Image.open(io.BytesIO(C.http_get(d["poster"]))).convert("RGB")
                    img.thumbnail((170, 250))
                except Exception as e:
                    dlog(f"poster failed: {e}")
            d = dict(d, _img=img)
            self.app.details_cache[it["title"]] = d
        return d

    def on_details(self, it, d, err):
        if it is not self.cur or err or d is None:
            return
        self.poster = None
        self.poster_lbl.configure(image="")
        if d.get("_img") is not None and HAVE_PIL:
            self.poster = ImageTk.PhotoImage(d["_img"])
            self.poster_lbl.configure(image=self.poster)
        if d.get("title"):
            self.info_lbl.configure(text=f"{d['title']} ({d.get('year') or '?'})\n{d.get('type', '')}\n\n{d.get('cast', '')}\n\n{d.get('id', '')}")
        else:
            self.info_lbl.configure(text="")

    # -- actions
    def download(self):
        sel = self.subtree.selection()
        if not sel or not self.cur:
            self.say("Select one or more subtitles first.")
            return
        dest = self.app.get_dest()
        if not dest:
            return
        src = self.app.source(self.cur["source"])
        picked = [self.subs[i] for i in sel]
        lang, opts = self.lang_var.get(), self.app.clean_opts()
        extract, z = self.app.cfg.get("extract", True), self.app.sevenzip()

        def work():
            msgs = []
            for s in picked:
                name, data = src.fetch(s)
                msgs.append(C.save_blob(data, name, dest, lang, opts, extract, z))
            return msgs

        self.say("Downloading...")
        self.app.bg(work, lambda r, e: self.say(("Error: " + friendly_error(e)) if e else f"{r[-1]}   ->  {dest}"))

    def preview(self):
        sel = self.subtree.selection()
        if not sel or not self.cur:
            self.say("Select a subtitle to preview.")
            return
        src, s = self.app.source(self.cur["source"]), self.subs[sel[0]]
        lang, opts, z = self.lang_var.get(), self.app.clean_opts(), self.app.sevenzip()
        self.say("Loading preview...")

        def work():
            name, data = src.fetch(s)
            return C.preview_text(data, name, lang, opts, z)

        def done(text, err):
            if err:
                self.say("Error: " + friendly_error(err))
            else:
                self.say("")
                TextDialog(self.app, T("Preview"), text)
        self.app.bg(work, done)

    def open_web(self):
        if self.cur:
            webbrowser.open(self.cur.get("url") or f"https://www.google.com/search?q={self.cur['title']}+subtitles")


# ------------------------------------------------------------ Subtitle Tools
class ToolsPage(Page):
    FPS = ["", "23.976", "24", "25", "29.97", "30"]

    def __init__(self, parent, app):
        super().__init__(parent, app)
        wrap = tk.Frame(self, bg=P["panel"])
        wrap.pack(fill="x", padx=24, pady=20)
        wrap.columnconfigure(1, weight=1)
        self.path = tk.StringVar()
        ttk.Label(wrap, text=T("Subtitle file:")).grid(row=0, column=0, sticky=anchor(), pady=6)
        ttk.Entry(wrap, textvariable=self.path).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(wrap, text=T("Browse..."), command=self.browse).grid(row=0, column=2)
        self.shift = tk.StringVar(value="0")
        ttk.Label(wrap, text=T("Shift timing (ms):")).grid(row=1, column=0, sticky=anchor(), pady=6)
        f = tk.Frame(wrap, bg=P["panel"])
        f.grid(row=1, column=1, sticky=anchor(), padx=8)
        ttk.Entry(f, textvariable=self.shift, width=10).pack(side=side(True))
        for d in (-1000, -500, 500, 1000):
            ttk.Button(f, text=f"{d:+d}", width=6, command=lambda d=d: self.nudge(d)).pack(side=side(True), padx=2)
        self.f_from, self.f_to = tk.StringVar(value=""), tk.StringVar(value="")
        ttk.Label(wrap, text=T("Frame rate: from")).grid(row=2, column=0, sticky=anchor(), pady=6)
        g = tk.Frame(wrap, bg=P["panel"])
        g.grid(row=2, column=1, sticky=anchor(), padx=8)
        ttk.Combobox(g, textvariable=self.f_from, values=self.FPS, width=8).pack(side=side(True))
        ttk.Label(g, text="  " + T("to") + "  ").pack(side=side(True))
        ttk.Combobox(g, textvariable=self.f_to, values=self.FPS, width=8).pack(side=side(True))
        self.over = tk.BooleanVar(value=False)
        ttk.Checkbutton(wrap, text=T("Replace the original (keeps a .bak copy)"), variable=self.over).grid(
            row=3, column=1, sticky=anchor(), padx=8, pady=6)
        options_row(wrap, app).grid(row=4, column=0, columnspan=3, sticky=anchor(), pady=6)
        ttk.Button(wrap, text=T("Apply"), command=self.apply).grid(row=5, column=1, sticky=anchor(), padx=8, pady=10)
        self.msg = ttk.Label(wrap, text="", wraplength=700)
        self.msg.grid(row=6, column=0, columnspan=3, sticky=anchor())

        # ---- rename videos to clean names
        ttk.Separator(wrap).grid(row=7, column=0, columnspan=3, sticky="ew", pady=(18, 4))
        ttk.Label(wrap, text=T("Rename video files to clean names:"), font=("Segoe UI", 10, "bold")).grid(
            row=8, column=0, columnspan=3, sticky=anchor())
        self.rn_folder = tk.StringVar()
        ttk.Entry(wrap, textvariable=self.rn_folder).grid(row=9, column=1, sticky="ew", padx=8, pady=6)
        ttk.Button(wrap, text=T("Browse..."), command=self.browse_folder).grid(row=9, column=2)
        rb = tk.Frame(wrap, bg=P["panel"])
        rb.grid(row=10, column=1, sticky=anchor(), padx=8)
        ttk.Button(rb, text=T("Preview renames"), command=self.preview_renames).pack(side=side(True))
        ttk.Button(rb, text=T("Apply renames"), command=self.apply_renames).pack(side=side(True), padx=6)
        ttk.Button(rb, text=T("Undo last rename"), command=self.undo_renames).pack(side=side(True))

    def browse_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.rn_folder.set(d)

    def _rename_plan(self):
        folder = self.rn_folder.get().strip()
        if not folder or not os.path.isdir(folder):
            self.msg.configure(text=T("Pick a folder with videos first."))
            return None
        return C.plan_renames([folder])

    def preview_renames(self):
        plan = self._rename_plan()
        if plan is None:
            return
        if not plan:
            self.msg.configure(text=T("Nothing to rename - all names already look clean."))
            return
        text = "\n".join(f"{os.path.basename(o)}\n   ->  {os.path.basename(n)}" for o, n in plan)
        TextDialog(self, T("Rename preview") + f" ({len(plan)})", text)

    def apply_renames(self):
        plan = self._rename_plan()
        if not plan:
            self.msg.configure(text=T("Nothing to rename."))
            return
        done = C.apply_renames(plan)
        self.msg.configure(text=T("Renamed") + f" {len(done)} " + T("file(s). Use Undo to restore."))

    def undo_renames(self):
        restored = C.undo_last_rename()
        self.msg.configure(text=(T("Restored") + f" {len(restored)} " + T("file(s)."))
                           if restored else T("Nothing to undo."))

    def browse(self):
        p = filedialog.askopenfilename(filetypes=[("Subtitles", "*.srt *.ass *.ssa *.vtt"), ("All files", "*.*")])
        if p:
            self.path.set(p)

    def nudge(self, d):
        try:
            v = int(float(self.shift.get() or 0))
        except ValueError:
            v = 0
        self.shift.set(str(v + d))

    def apply(self):
        p = self.path.get().strip()
        if not p or not os.path.isfile(p):
            self.msg.configure(text=T("Pick a subtitle file first."))
            return
        try:
            shift = int(float(self.shift.get() or 0))
            ff = float(self.f_from.get()) if self.f_from.get() else None
            ft = float(self.f_to.get()) if self.f_to.get() else None
        except ValueError:
            self.msg.configure(text="Shift and frame rates must be numbers.")
            return
        lang, opts, over = self.app.cfg.get("language", "English"), self.app.clean_opts(), self.over.get()
        self.app.bg(lambda: C.transform_file(p, shift, ff, ft, lang, opts, over),
                    lambda r, e: self.msg.configure(text=("Error: " + friendly_error(e)) if e else r[1]))


# --------------------------------------------------------------- Settings page
SOURCE_NOTES = {
    "OpenSubtitles": "official API · needs API key + free account · supports file-hash matching",
    "SubSource": "official API · needs free API key",
    "Subf2m": "unofficial (web scraping) · off by default · may be blocked",
}
UI_LANGS = {"English": "en", "\u0627\u0644\u0639\u0631\u0628\u064a\u0629": "ar"}
THEMES = {"System": "system", "Light": "light", "Dark": "dark"}


class SettingsPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        c = app.cfg
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=(16, 6))
        tabs = {}
        for key, title in (("general", "General"), ("sources", "Sources"), ("subs", "Subtitles"),
                           ("arch", "Archives"), ("adv", "Advanced"), ("about", "About")):
            f = tk.Frame(self.nb, bg=P["panel"])
            f.columnconfigure(1, weight=1)
            self.nb.add(f, text=T(title))
            tabs[key] = f

        # ---- General
        g, r = tabs["general"], [0]

        def row(frame, label, widget, counter=r):
            ttk.Label(frame, text=label).grid(row=counter[0], column=0, sticky=anchor(), padx=(16, 12), pady=6)
            widget.grid(row=counter[0], column=1, sticky="ew", padx=(0, 16), pady=6)
            counter[0] += 1
            return widget

        self.ui_lang = tk.StringVar(value=next(k for k, v in UI_LANGS.items() if v == c.get("ui_lang", "en")))
        row(g, T("Interface language"), ttk.Combobox(g, textvariable=self.ui_lang, values=list(UI_LANGS), state="readonly"))
        self.theme = tk.StringVar(value=next(k for k, v in THEMES.items() if v == c.get("theme", "system")))
        row(g, T("Theme"), ttk.Combobox(g, textvariable=self.theme, values=list(THEMES), state="readonly"))
        self.lang = tk.StringVar(value=c.get("language", "English"))
        row(g, T("Default language"), ttk.Combobox(g, textvariable=self.lang, values=list(LANGS), state="readonly"))
        self.dest = tk.StringVar(value=c.get("dest") or os.path.join(os.path.expanduser("~"), "Downloads"))
        f = tk.Frame(g, bg=P["panel"])
        f.columnconfigure(0, weight=1)
        ttk.Entry(f, textvariable=self.dest).grid(row=0, column=0, sticky="ew")
        ttk.Button(f, text=T("Browse..."), command=self.pick_dest).grid(row=0, column=1, padx=(6, 0))
        row(g, T("Download folder"), f)
        self.ask = tk.BooleanVar(value=c.get("ask_dest", False))
        row(g, "", ttk.Checkbutton(g, text=T("Ask where to save every time"), variable=self.ask))
        self.extract = tk.BooleanVar(value=c.get("extract", True))
        row(g, "", ttk.Checkbutton(g, text=T("Extract .zip files after download"), variable=self.extract))
        self.updates = tk.BooleanVar(value=c.get("check_updates", True))
        row(g, "", ttk.Checkbutton(g, text=T("Check for updates on start"), variable=self.updates))

        # ---- Sources
        s = tabs["sources"]
        self.order = C.ordered_sources(c)
        on = set(C.enabled_sources(c))
        self.enabled = {n: tk.BooleanVar(value=n in on) for n in SOURCE_ORDER}
        self.status_lbls, self.status = {}, {}
        self.rows = tk.Frame(s, bg=P["panel"])
        self.rows.pack(fill="x", padx=16, pady=(12, 6))
        self.build_rows()
        ttk.Label(s, text=T("Unofficial sources scrape websites: they can break when a site changes, "
                            "may be blocked, and stay off until you enable them."),
                  foreground=P["muted"], wraplength=660, justify="left").pack(fill="x", padx=16, pady=(2, 0))
        ttk.Separator(s).pack(fill="x", padx=16, pady=6)
        cred = tk.Frame(s, bg=P["panel"])
        cred.pack(fill="x", padx=16)
        cred.columnconfigure(1, weight=1)
        ttk.Label(cred, text=T("Credentials"), font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky=anchor())
        self.ss_key = tk.StringVar(value=C.get_secret(c, "subsource_key"))
        self.os_key = tk.StringVar(value=C.get_secret(c, "os_key"))
        self.os_user = tk.StringVar(value=c.get("os_user", ""))
        self.os_pass = tk.StringVar(value=C.get_secret(c, "os_pass"))
        for i, (label, var, secret, url) in enumerate((
                ("SubSource API key", self.ss_key, True, "https://subsource.net"),
                ("OpenSubtitles API key", self.os_key, True, "https://www.opensubtitles.com/consumers"),
                ("OpenSubtitles username", self.os_user, False, None),
                ("OpenSubtitles password", self.os_pass, True, None)), 1):
            ttk.Label(cred, text=label).grid(row=i, column=0, sticky=anchor(), pady=4, padx=(0, 12))
            ttk.Entry(cred, textvariable=var, show="*" if secret else "").grid(row=i, column=1, sticky="ew", pady=4)
            if url:
                ttk.Button(cred, text="Get key", command=lambda u=url: webbrowser.open(u)).grid(row=i, column=2, padx=(6, 0))
        store_note = ("Keys and the password are stored in the Windows Credential Manager, not in files."
                      if C.secrets_backend() == "keyring" else
                      "Keys and the password are stored on this PC in config.json (plain text). "
                      "Install the 'keyring' package to store them in the Windows Credential Manager instead.")
        ttk.Label(cred, text=store_note, foreground=P["muted"], wraplength=640).grid(
            row=5, column=0, columnspan=3, sticky=anchor(), pady=(6, 0))

        # ---- Subtitles
        t = tabs["subs"]
        o = tk.Frame(t, bg=P["panel"])
        o.pack(fill="x", padx=16, pady=12)
        for key, text in (("utf8", "Convert to UTF-8"), ("to_srt", "Convert to SRT"), ("ads", "Remove ads / watermarks"),
                          ("hi", "Remove hearing-impaired tags"), ("bom", "Add BOM (older TVs/players)")):
            ttk.Checkbutton(o, text=T(text), variable=app.clean_vars[key], command=app.save_clean).pack(anchor=anchor(), pady=3)
        self.use_hash = tk.BooleanVar(value=c.get("use_hash", True))
        ttk.Checkbutton(o, text=T("Use file hash when possible (exact sync)"), variable=self.use_hash).pack(anchor=anchor(), pady=3)
        self.weak_save = tk.BooleanVar(value=c.get("weak_save", False))
        ttk.Checkbutton(o, text=T("Save weak matches automatically"), variable=self.weak_save).pack(anchor=anchor(), pady=3)
        l2 = tk.Frame(o, bg=P["panel"])
        l2.pack(anchor=anchor(), pady=8)
        ttk.Label(l2, text=T("Also download a second language:")).pack(side=side(True))
        self.lang2 = tk.StringVar(value=c.get("language2") or T("None"))
        ttk.Combobox(l2, textvariable=self.lang2, values=[T("None")] + list(LANGS), state="readonly", width=20).pack(side=side(True), padx=8)

        # ---- Archives
        a = tabs["arch"]
        ar = tk.Frame(a, bg=P["panel"])
        ar.pack(fill="x", padx=16, pady=12)
        ar.columnconfigure(1, weight=1)
        self.z_on = tk.BooleanVar(value=c.get("sevenzip_on", True))
        ttk.Checkbutton(ar, text=T("Unpack RAR / 7z files with 7-Zip"), variable=self.z_on).grid(row=0, column=0, columnspan=3, sticky=anchor(), pady=4)
        self.z_path = tk.StringVar(value=c.get("sevenzip_path", ""))
        ttk.Label(ar, text=T("7-Zip path")).grid(row=1, column=0, sticky=anchor(), padx=(0, 12), pady=6)
        ttk.Entry(ar, textvariable=self.z_path).grid(row=1, column=1, sticky="ew")
        ttk.Button(ar, text=T("Browse..."), command=self.pick_7z).grid(row=1, column=2, padx=(6, 0))
        self.z_lbl = ttk.Label(ar, text="", wraplength=640, foreground=P["muted"])
        self.z_lbl.grid(row=2, column=0, columnspan=3, sticky=anchor(), pady=8)
        ttk.Button(ar, text="Re-check", command=self.check_7z).grid(row=3, column=0, sticky=anchor())
        self.check_7z()

        # ---- Advanced
        d = tabs["adv"]
        ttk.Label(d, text=T("Site addresses (change them if a site moves)"), font=("Segoe UI", 10, "bold")).pack(anchor=anchor(), padx=16, pady=(12, 4))
        site_frame = tk.Frame(d, bg=P["panel"])
        site_frame.pack(fill="x", padx=16)
        site_frame.columnconfigure(1, weight=1)
        self.sites, saved = {}, c.get("sites", {})
        defaults = {n: v[0] for n, v in C.SITES.items()}
        self.site_defaults = defaults
        for i, (name, base) in enumerate(defaults.items()):
            self.sites[name] = tk.StringVar(value=saved.get(name) or base)
            ttk.Label(site_frame, text=name).grid(row=i, column=0, sticky=anchor(), padx=(0, 12), pady=4)
            ttk.Entry(site_frame, textvariable=self.sites[name]).grid(row=i, column=1, sticky="ew", pady=4)
        bt = tk.Frame(d, bg=P["panel"])
        bt.pack(fill="x", padx=16, pady=12)
        ttk.Button(bt, text=T("Reset site addresses"), command=self.reset_sites).pack(side=side(True))
        ttk.Button(bt, text=T("Open debug log"), command=self.open_log).pack(side=side(True), padx=6)
        ttk.Button(bt, text=T("Open data folder"), command=lambda: self.open_path(C.data_dir())).pack(side=side(True))
        ttk.Label(d, text=("Portable mode: settings are kept in the 'data' folder next to SubGrab.exe." if C.is_portable()
                           else "Settings folder: " + C.data_dir() + "   (create an empty portable.txt next to SubGrab.exe for portable mode)"),
                  foreground=P["muted"], wraplength=700).pack(anchor=anchor(), padx=16)

        # ---- About
        b = tabs["about"]
        ttk.Label(b, text=f"{APP_NAME} {VERSION}", font=("Segoe UI", 16, "bold")).pack(anchor=anchor(), padx=16, pady=(16, 4))
        ttk.Label(b, text="Subtitle downloader - OpenSubtitles, SubSource, Subf2m and more.\n"
                          "GPL v3 licensed. 7-Zip (LGPL) is used for RAR/7z when available.", wraplength=700).pack(anchor=anchor(), padx=16)
        self.upd_lbl = ttk.Label(b, text="")
        ttk.Button(b, text=T("Check for updates"), command=self.check_updates).pack(anchor=anchor(), padx=16, pady=10)
        self.upd_lbl.pack(anchor=anchor(), padx=16)
        if "YOUR-USERNAME" not in GITHUB_REPO:
            ttk.Button(b, text="Open GitHub page", command=lambda: webbrowser.open(f"https://github.com/{GITHUB_REPO}")).pack(anchor=anchor(), padx=16, pady=4)

        # ---- bottom bar
        bar = tk.Frame(self, bg=P["panel"])
        bar.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Button(bar, text=T("Save"), command=self.save).pack(side=side(True))
        self.msg = ttk.Label(bar, text="")
        self.msg.pack(side=side(True), padx=12)
        self.restart_btn = ttk.Button(bar, text=T("Restart now"), command=app.restart)

    # -- sources tab
    def build_rows(self):
        for w in self.rows.winfo_children():
            w.destroy()
        self.status_lbls = {}
        for i, name in enumerate(self.order):
            fr = tk.Frame(self.rows, bg=P["panel"])
            fr.pack(fill="x", pady=2)
            ttk.Checkbutton(fr, text=name, variable=self.enabled[name], width=15).pack(side=side(True))
            ttk.Button(fr, text="\u2191", width=3, command=lambda i=i: self.move(i, -1)).pack(side=side(True))
            ttk.Button(fr, text="\u2193", width=3, command=lambda i=i: self.move(i, 1)).pack(side=side(True), padx=(2, 8))
            ttk.Button(fr, text=T("Test"), command=lambda n=name: self.test(n)).pack(side=side(True))
            lbl = ttk.Label(fr, text=self.status.get(name) or SOURCE_NOTES.get(name, ""), foreground=P["muted"], wraplength=520)
            lbl.pack(side=side(True), padx=10)
            self.status_lbls[name] = lbl

    def move(self, i, d):
        j = i + d
        if 0 <= j < len(self.order):
            self.order[i], self.order[j] = self.order[j], self.order[i]
            self.build_rows()

    def test(self, name):
        cfg = dict(self.app.cfg)
        cfg.update(self.collect())
        src = C.build_sources(cfg)[name]
        self.status[name] = "testing..."
        self.status_lbls[name].configure(text="testing...")

        def done(res, err):
            ok, msg = (False, friendly_error(err)) if err else res
            self.status[name] = ("\u2713 " if ok else "\u2717 ") + msg
            if name in self.status_lbls:
                try:
                    self.status_lbls[name].configure(text=self.status[name])
                except Exception:
                    pass
        self.app.bg(lambda: C.test_source(src), done)

    # -- misc tabs
    def pick_dest(self):
        d = filedialog.askdirectory(initialdir=self.dest.get() or None)
        if d:
            self.dest.set(d)

    def pick_7z(self):
        p = filedialog.askopenfilename(filetypes=[("7z.exe", "7z.exe"), ("All files", "*.*")])
        if p:
            self.z_path.set(p)
            self.check_7z()

    def check_7z(self):
        exe = C.find_7z(self.z_path.get().strip())
        bundled = os.path.isfile(os.path.join(getattr(sys, "_MEIPASS", ""), "7zip", "7z.exe"))
        if exe:
            self.z_lbl.configure(text=f"\u2713 Found: {exe}" + ("  (bundled with SubGrab)" if bundled else ""))
        else:
            self.z_lbl.configure(text="\u2717 7-Zip not found. Install it from 7-zip.org, or point to 7z.exe above. "
                                      "RAR/7z downloads are skipped until then (zip and plain .srt always work).")

    def reset_sites(self):
        for n, v in self.site_defaults.items():
            self.sites[n].set(v)

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
        self.upd_lbl.configure(text="Checking...")

        def done(res, err):
            if err:
                self.upd_lbl.configure(text="Could not check: " + friendly_error(err))
            elif res:
                self.upd_lbl.configure(text=f"Version {res[0]} is available: {res[1]}")
                webbrowser.open(res[1])
            else:
                self.upd_lbl.configure(text="You are up to date." if "YOUR-USERNAME" not in GITHUB_REPO
                                       else "Update checking is off until GITHUB_REPO is set in subgrab_core.py.")
        self.app.bg(C.check_update, done)

    # -- save
    def collect(self):
        lang2 = self.lang2.get()
        return {
            "language": self.lang.get(), "dest": self.dest.get(), "ask_dest": self.ask.get(), "extract": self.extract.get(),
            "check_updates": self.updates.get(), "order": list(self.order),
            "enabled": {n: v.get() for n, v in self.enabled.items()},
            "os_user": self.os_user.get().strip(),
            "use_hash": self.use_hash.get(), "weak_save": self.weak_save.get(),
            "language2": "" if lang2 in (T("None"), "None") else lang2,
            "sevenzip_on": self.z_on.get(), "sevenzip_path": self.z_path.get().strip(),
            "sites": {n: v.get().strip() for n, v in self.sites.items() if v.get().strip() != self.site_defaults[n]},
        }

    def save(self):
        old = (self.app.cfg.get("ui_lang", "en"), self.app.cfg.get("theme", "system"))
        new_cfg = self.collect()
        new_cfg["ui_lang"] = UI_LANGS[self.ui_lang.get()]
        new_cfg["theme"] = THEMES[self.theme.get()]
        self.app.cfg.update(new_cfg)
        for name, var in (("subsource_key", self.ss_key), ("os_key", self.os_key), ("os_pass", self.os_pass)):
            C.set_secret(self.app.cfg, name, var.get())
        C.save_config(self.app.cfg)
        self.app.build_sources()
        changed = old != (new_cfg["ui_lang"], new_cfg["theme"])
        self.msg.configure(text=T("Saved.") + ("  " + T("Restart to apply language / theme changes.") if changed else ""))
        if changed:
            self.restart_btn.pack(side=side(True))


# --------------------------------------------------------------------- the app
def enable_file_drop(root, callback):
    """Windows drag & drop of files/folders onto the window (ctypes, no extra packages)."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32, shell32 = ctypes.windll.user32, ctypes.windll.shell32
        root.update_idletasks()
        hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
        WM_DROPFILES, GWL_WNDPROC = 0x0233, -4
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        user32.CallWindowProcW.restype = LRESULT
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        shell32.DragQueryFileW.restype = wintypes.UINT
        shell32.DragFinish.argtypes = [wintypes.HANDLE]
        old = [None]

        def proc(h, msg, wp, lp):
            if msg == WM_DROPFILES:
                paths = []
                for i in range(shell32.DragQueryFileW(wp, 0xFFFFFFFF, None, 0)):
                    n = shell32.DragQueryFileW(wp, i, None, 0)
                    buf = ctypes.create_unicode_buffer(n + 1)
                    shell32.DragQueryFileW(wp, i, buf, n + 1)
                    paths.append(buf.value)
                shell32.DragFinish(wp)
                root.after(0, callback, paths)
                return 0
            return user32.CallWindowProcW(old[0], h, msg, wp, lp)

        cb = WNDPROC(proc)
        root._drop_proc = cb  # keep a reference or it is garbage-collected
        shell32.DragAcceptFiles(hwnd, True)
        old[0] = user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC, ctypes.cast(cb, ctypes.c_void_p))
        return True
    except Exception as e:  # drag & drop is a bonus - never fatal
        dlog(f"drag & drop unavailable: {e!r}")
        return False


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = C.load_config()
        configure_ui(self.cfg)
        self.title(APP_NAME)
        self.geometry("1140x740")
        self.minsize(920, 600)
        self.configure(bg=P["bg"])
        self.q = queue.Queue()
        self.pages, self.navs, self.history, self.current = {}, {}, [], None
        self.details_cache = {}
        c = dict(DEFAULT_CLEAN, **self.cfg.get("clean", {}))
        self.clean_vars = {k: tk.BooleanVar(value=bool(v)) for k, v in c.items()}
        self.srcs = {}
        self.build_sources()
        apply_style(self)

        self.logo = None
        if LOGO_PNG_B64:
            try:
                self.logo = tk.PhotoImage(data=LOGO_PNG_B64)
                self.iconphoto(True, self.logo)
            except Exception as e:
                dlog(f"logo failed: {e!r}")

        sidebar = tk.Frame(self, bg=P["bg"], width=270)
        sidebar.pack(side=side(True), fill="y")
        sidebar.pack_propagate(False)
        head = tk.Frame(sidebar, bg=P["bg"])
        head.pack(fill="x", pady=(14, 10))
        back = tk.Label(head, text="\u2192" if UI["rtl"] else "\u2190", bg=P["bg"], fg=P["muted"], font=("Segoe UI", 14), cursor="hand2", padx=18)
        back.pack(anchor=anchor())
        back.bind("<Button-1>", lambda e: self.go_back())
        brand = tk.Frame(head, bg=P["bg"])
        brand.pack(anchor=anchor(), padx=16, pady=(10, 0))
        if self.logo:
            small = self.logo.subsample(max(1, self.logo.width() // 32))
            self._small = small
            tk.Label(brand, image=small, bg=P["bg"]).pack(side=side(True))
        tk.Label(brand, text=f"  {APP_NAME}", bg=P["bg"], fg=P["fg"], font=("Segoe UI", 14, "bold")).pack(side=side(True))

        self.content = tk.Frame(self, bg=P["panel"], highlightthickness=1, highlightbackground=P["border"])
        self.content.pack(side=side(False), fill="both", expand=True, pady=(8, 0))
        self.banner = tk.Label(self.content, bg=P["accent"], fg="#ffffff", cursor="hand2", font=("Segoe UI", 10, "bold"), pady=6)
        self.host = tk.Frame(self.content, bg=P["panel"])
        self.host.pack(fill="both", expand=True)

        def add(key, icon, text, factory, bottom=False):
            nav = NavItem(sidebar, icon, T(text), lambda k=key: self.show(k))
            nav.pack(side="bottom" if bottom else "top", fill="x", padx=6, pady=1)
            self.navs[key] = nav
            self.pages[key] = factory()

        add("auto", "\u25B6", "Auto Folder", lambda: AutoPage(self.host, self))
        add("search", "\u2302", "Search", lambda: SearchPage(self.host, self))
        add("tools", "\u21C4", "Subtitle Tools", lambda: ToolsPage(self.host, self))
        add("set", "\u2699", "Settings", lambda: SettingsPage(self.host, self), bottom=True)

        if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
            self.after(200, lambda: self.pages["auto"].set_paths([sys.argv[1]]))
        self.show("auto", push=False)
        self.after(80, self.poll)
        self.after(400, lambda: enable_file_drop(self, self.on_drop))
        if self.cfg.get("check_updates", True):
            self.after(3000, lambda: self.bg(C.check_update, self.on_update))

    # -- settings-derived helpers
    def build_sources(self):
        self.srcs = C.build_sources(self.cfg)

    def source(self, name):
        return self.srcs[name]

    def clean_opts(self):
        return {k: v.get() for k, v in self.clean_vars.items()}

    def save_clean(self):
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

    def get_dest(self):
        if self.cfg.get("ask_dest"):
            return filedialog.askdirectory(title="Save subtitles to...") or None
        return self.cfg.get("dest") or os.path.join(os.path.expanduser("~"), "Downloads")

    # -- navigation
    def show(self, key, push=True):
        if self.current == key:
            return
        if push and self.current:
            self.history.append(self.current)
        if self.current:
            self.pages[self.current].pack_forget()
            self.navs[self.current].set_active(False)
        self.current = key
        self.pages[key].pack(fill="both", expand=True)
        self.navs[key].set_active(True)
        self.pages[key].on_show()

    def go_back(self):
        if self.history:
            self.show(self.history.pop(), push=False)

    # -- events
    def on_drop(self, paths):
        self.show("auto")
        self.pages["auto"].set_paths(paths)

    def on_update(self, res, err):
        if res and not err:
            self.banner.configure(text=f"SubGrab {res[0]} is available - click to download")
            self.banner.bind("<Button-1>", lambda e: webbrowser.open(res[1]))
            self.banner.pack(side="top", fill="x", before=self.host)

    def restart(self):
        try:
            args = [sys.executable] + ([] if getattr(sys, "frozen", False) else [os.path.abspath(sys.argv[0])])
            subprocess.Popen(args)
        finally:
            self.destroy()

    # -- threading helpers: UI work only ever runs on the Tk thread
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
        self.after(80, self.poll)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
