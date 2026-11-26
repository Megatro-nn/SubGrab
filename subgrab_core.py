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
SubGrab core - everything except the Tk interface, so it can be unit-tested anywhere.

Sources:  OpenSubtitles.com (API key), SubSource (API key), Subf2m (no key).
Features: file-hash matching, release-name scoring, encoding fix (UTF-8), ASS/VTT -> SRT,
          ad / hearing-impaired cleanup, RAR/7z unpacking via 7-Zip, timing tools.
"""
import codecs
import difflib
import html as htmllib
import http.cookiejar
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

VERSION = "1.0.0"
APP_NAME = "SubGrab"
GITHUB_REPO = "Megatro-nn/SubGrab"  # <-- set this before publishing (used by the update checker)
SS_BASE = "https://api.subsource.net/api/v1"
OS_BASE = "https://api.opensubtitles.com/api/v1"

VIDEO_EXT = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".mpg", ".mpeg", ".ts", ".webm", ".flv"}
SUB_EXT = (".srt", ".ass", ".ssa", ".sub", ".vtt")
ARCHIVE_EXT = (".zip", ".rar", ".7z", ".srt", ".ass", ".ssa", ".sub", ".vtt")
WEAK = 0.40  # release-match quality below this is a "weak match"

# name: file suffix, SubSource language, language-page slug, words seen in listings, legacy code pages
LANGS = {
    "English": {"suffix": "en", "ss": "english", "slug": "english", "words": ["english"], "cp": []},
    "Arabic": {"suffix": "ar", "ss": "arabic", "slug": "arabic", "words": ["arabic"], "cp": ["cp1256"]},
    "Persian": {"suffix": "fa", "ss": "farsi_persian", "slug": "farsi_persian", "words": ["persian", "farsi"], "cp": ["cp1256"]},
    "French": {"suffix": "fr", "ss": "french", "slug": "french", "words": ["french"], "cp": []},
    "Spanish": {"suffix": "es", "ss": "spanish", "slug": "spanish", "words": ["spanish"], "cp": []},
    "German": {"suffix": "de", "ss": "german", "slug": "german", "words": ["german"], "cp": []},
    "Italian": {"suffix": "it", "ss": "italian", "slug": "italian", "words": ["italian"], "cp": []},
    "Portuguese (Brazil)": {"suffix": "pt-BR", "ss": "brazilian_portuguese", "slug": "brazillian-portuguese", "words": ["brazil"], "cp": []},
    "Turkish": {"suffix": "tr", "ss": "turkish", "slug": "turkish", "words": ["turkish"], "cp": ["cp1254"]},
    "Russian": {"suffix": "ru", "ss": "russian", "slug": "russian", "words": ["russian"], "cp": ["cp1251"]},
    "Indonesian": {"suffix": "id", "ss": "indonesian", "slug": "indonesian", "words": ["indonesian"], "cp": []},
    "Dutch": {"suffix": "nl", "ss": "dutch", "slug": "dutch", "words": ["dutch"], "cp": []},
    "Hindi": {"suffix": "hi", "ss": "hindi", "slug": "hindi", "words": ["hindi"], "cp": []},
}

# web-scraped sites: name -> (default base url, search path templates, movies_only)
SITES = {
    "Subf2m": ("https://subf2m.co", ["/subtitles/searchbytitle?query={q}&l="], False),
}
SOURCE_ORDER = ["OpenSubtitles", "SubSource", "Subf2m"]
KEY_SOURCES = ("OpenSubtitles", "SubSource")
# Official APIs first; web-scraped sources are opt-in: they break easily when the
# sites change, may be blocked, and may conflict with those sites' terms of use.
OFFICIAL_SOURCES = ["OpenSubtitles", "SubSource"]
SCRAPER_SOURCES = ["Subf2m"]
DEFAULT_ENABLED = ["OpenSubtitles", "SubSource"]

SE_RE = re.compile(r"[Ss](\d{1,2})[ ._-]?[Ee](\d{1,3})")
# S01E01 plus an optional second episode number: S01E01E02, S01E01-E02, S01E01-02
MULTI_SE_RE = re.compile(r"[Ss](\d{1,2})[ ._-]?[Ee](\d{1,3})(?:(?:\s?-?\s?[Ee]|-)(\d{1,3}))?(?!\d)")
ALT_RE = re.compile(r"(?<!\d)(\d{1,2})x(\d{2,3})(?!\d)")
YEAR_RE = re.compile(r"(?<![\d])(19\d\d|20\d\d)(?![\d])")
# anime-style absolute numbering: "[Group] Show - 03 [1080p]", "Show - 12v2"
ANIME_RE = re.compile(r"^(?:\[[^\]\[]{1,20}\]\s*)?(?P<title>.+?)\s+-\s+(?P<ep>\d{1,4})(?:v\d+)?(?:\s*[\[\(].*)?$", re.I)
_EDITIONS = [(r"director'?s? ?cut", "Director's Cut"), (r"extended( edition| cut| version)?", "Extended"),
             (r"unrated", "Unrated"), (r"theatrical( cut| edition| version)?", "Theatrical"),
             (r"remaster(?:ed)?", "Remastered"), (r"special edition", "Special Edition"),
             (r"final cut", "Final Cut"), (r"redux", "Redux"), (r"criterion( edition| collection)?", "Criterion"),
             (r"\bimax\b", "IMAX"), (r"ultimate( edition)?", "Ultimate Edition"),
             (r"anniversary( edition)?", "Anniversary Edition")]
EDITION_RES = [(re.compile(p, re.I), label) for p, label in _EDITIONS]


def edition_of(text):
    """Canonical edition label ('Extended', 'Director's Cut', ...) or None."""
    t = re.sub(r"[._]+", " ", text or "")
    for rx, label in EDITION_RES:
        if rx.search(t):
            return label
    return None
SEASON_DIR_RE = re.compile(r"^(season|series|s)[ ._-]?\d+$", re.I)
ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth",
            "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth",
            "seventeenth", "eighteenth", "nineteenth", "twentieth"]
IMDB_RE = re.compile(r"^tt\d{6,10}$", re.I)
DEFAULT_CLEAN = {"utf8": True, "to_srt": True, "ads": False, "hi": False, "bom": False}


# ------------------------------------------------------------ paths / config
def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def is_portable():
    return os.path.exists(os.path.join(app_dir(), "portable.txt"))


def data_dir():
    if is_portable():
        d = os.path.join(app_dir(), "data")
    else:
        d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def load_config():
    try:
        with open(os.path.join(data_dir(), "config.json"), "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return {}
    if migrate_secrets(cfg):
        save_config(cfg)
    return cfg


def save_config(cfg):
    try:
        with open(os.path.join(data_dir(), "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ------------------------------------------------------- secure secret storage
# API keys and passwords are kept in the Windows Credential Manager (through the
# optional `keyring` package). When keyring is not installed or no OS backend is
# available, secrets fall back to config.json as before.
SECRET_KEYS = ("subsource_key", "os_key", "os_pass")
KEYRING_SERVICE = APP_NAME

try:
    import keyring as _keyring
except Exception:  # package not installed, or import failed on this machine
    _keyring = None


def secrets_backend():
    """'keyring' when the OS credential store is usable, otherwise 'config'."""
    if _keyring is None:
        return "config"
    try:
        _keyring.get_keyring()
        return "keyring"
    except Exception:
        return "config"


def get_secret(cfg, name, default=""):
    """Read a secret: credential store first, then the config dict."""
    if _keyring is not None:
        try:
            v = _keyring.get_password(KEYRING_SERVICE, name)
            if v:
                return v
        except Exception as e:
            dlog(f"keyring read {name} failed: {e!r}")
    return cfg.get(name, default)


def set_secret(cfg, name, value):
    """Store a secret and remove any plaintext copy from cfg.
    Returns 'keyring' or 'config' - where the value actually landed."""
    value = (value or "").strip()
    if _keyring is not None:
        try:
            if value:
                _keyring.set_password(KEYRING_SERVICE, name, value)
            else:
                try:
                    _keyring.delete_password(KEYRING_SERVICE, name)
                except Exception:
                    pass
            cfg.pop(name, None)
            return "keyring"
        except Exception as e:
            dlog(f"keyring write {name} failed: {e!r}")
    if value:
        cfg[name] = value
    else:
        cfg.pop(name, None)
    return "config"


def migrate_secrets(cfg):
    """One-time move of plaintext secrets from config.json into the credential
    store. Returns True when cfg changed (the caller should save_config)."""
    if _keyring is None:
        return False
    moved = False
    for name in SECRET_KEYS:
        if cfg.get(name):
            if set_secret(cfg, name, cfg[name]) == "keyring":
                moved = True
    return moved


def dlog(msg):
    try:
        p = os.path.join(data_dir(), "debug.log")
        if os.path.exists(p) and os.path.getsize(p) > 512 * 1024:
            os.replace(p, p + ".old")
        with open(p, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(msg) + "\n")
    except Exception:
        pass


# ----------------------------------------------------------- filename parsing
def clean_title(text):
    text = re.sub(r"[\[\(].*?[\]\)]", " ", text)
    text = re.sub(r"[._]+", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -(")


class VideoInfo:
    def __init__(self, path):
        self.path = path
        self.stem = os.path.splitext(os.path.basename(path))[0]
        self.season = self.episode = None
        self.episode_end = None  # set for multi-episode files (S01E01E02)
        self.absolute = False    # anime-style absolute episode numbering (no season in the name)
        self.edition = None      # 'Extended', "Director's Cut", ... when the name says one
        self.year = None
        self.title = ""
        self._hash = False  # False = not computed yet
        self.parse()

    @property
    def is_episode(self):
        return self.season is not None and self.episode is not None

    @property
    def moviehash(self):
        if self._hash is False:
            try:
                self._hash = opensubtitles_hash(self.path)
            except OSError:
                self._hash = None
        return self._hash

    def parse(self):
        stem = self.stem
        m = MULTI_SE_RE.search(stem) or ALT_RE.search(stem)
        ym = YEAR_RE.search(stem)
        cut = len(stem)
        if m:
            self.season, self.episode = int(m.group(1)), int(m.group(2))
            if m.re is MULTI_SE_RE and m.group(3):
                end = int(m.group(3))
                if self.episode < end <= self.episode + 8:
                    self.episode_end = end
            cut = m.start()
        else:
            am = ANIME_RE.match(stem)
            if am and not (ym and int(am.group("ep")) == int(ym.group(1))) and int(am.group("ep")) < 1900:
                self.season, self.episode, self.absolute = 1, int(am.group("ep")), True
                cut = am.start("title") + len(am.group("title"))
            elif ym:
                cut = ym.start()
        if ym:
            self.year = int(ym.group(1))
            if ym.start() < cut:
                cut = ym.start()
        self.title = clean_title(stem[:cut]) or self.title_from_folders()
        self.edition = edition_of(stem)
        if self.year is None and not self.is_episode:
            fy = YEAR_RE.search(os.path.basename(os.path.dirname(self.path)))
            if fy:
                self.year = int(fy.group(1))

    def title_from_folders(self):
        folder = os.path.dirname(self.path)
        for _ in range(3):
            name = os.path.basename(folder)
            if name and not SEASON_DIR_RE.match(name):
                cut = len(name)
                for rx in (SE_RE, YEAR_RE):
                    mm = rx.search(name)
                    if mm:
                        cut = min(cut, mm.start())
                t = clean_title(name[:cut])
                if t:
                    return t
            parent = os.path.dirname(folder)
            if parent == folder:
                break
            folder = parent
        return self.stem

    def label(self):
        if self.is_episode:
            tag = f"S{self.season:02d}E{self.episode:02d}"
            if self.episode_end:
                tag += f"E{self.episode_end:02d}"
            return f"{self.title}  {tag}"
        return f"{self.title}" + (f" ({self.year})" if self.year else "")


def find_videos(folder, recursive=True):
    found = []
    if recursive:
        for root, _d, files in os.walk(folder):
            for f in files:
                if os.path.splitext(f)[1].lower() in VIDEO_EXT:
                    found.append(os.path.join(root, f))
    else:
        for f in os.listdir(folder):
            p = os.path.join(folder, f)
            if os.path.isfile(p) and os.path.splitext(f)[1].lower() in VIDEO_EXT:
                found.append(p)
    return sorted(found, key=lambda p: p.lower())


def videos_from_paths(paths, recursive=True):
    """Folders and/or video files (drag & drop) -> sorted unique list of video paths."""
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += find_videos(p, recursive)
        elif os.path.splitext(p)[1].lower() in VIDEO_EXT:
            out.append(p)
    return sorted(dict.fromkeys(out), key=lambda p: p.lower())


def existing_sub(video_path, suffix):
    stem = os.path.splitext(video_path)[0]
    return any(os.path.exists(f"{stem}.{suffix}{e}") for e in SUB_EXT)


# ------------------------------------------------------------- file renaming
INVALID_CHARS = re.compile(r'[\\/:*?"<>|]+')


def canonical_name(info):
    """Clean display name for a video: 'Title (Year)' / 'Title - S01E02' (+ the
    edition and the release tags the original name carried). '' when there is
    nothing usable to build from."""
    base = INVALID_CHARS.sub(" ", info.title).strip().rstrip(".")
    if not base:
        return ""
    if info.is_episode:
        if info.absolute:
            tag = f"{info.episode:02d}"
        else:
            tag = f"S{info.season:02d}E{info.episode:02d}"
            if info.episode_end:
                tag += f"E{info.episode_end:02d}"
        name = f"{base} - {tag}"
    else:
        name = base + (f" ({info.year})" if info.year else "")
    if info.edition and info.edition.lower() not in name.lower():
        name += " " + info.edition
    attrs = release_attrs(info.stem)
    extras = [attrs["res"], attrs["src"], attrs["codec"]]
    tail = " ".join(e for e in extras if e)
    if attrs["group"]:
        tail += (" " if tail else "") + "-" + attrs["group"]
    return (name + (" " + tail if tail else "")).strip()


def plan_renames(paths, recursive=True):
    """[(old_path, new_path)] for videos (and their sidecar subtitles) whose clean
    canonical name differs from the current one. Skips collisions."""
    plan, targets = [], set()
    for p in videos_from_paths(paths, recursive):
        info = VideoInfo(p)
        new_stem = canonical_name(info)
        if not new_stem or new_stem == info.stem:
            continue
        folder = os.path.dirname(p)
        pairs = [(p, os.path.join(folder, new_stem + os.path.splitext(p)[1]))]
        try:
            for f in os.listdir(folder):
                if f.startswith(info.stem + ".") and os.path.splitext(f)[1].lower() in SUB_EXT:
                    pairs.append((os.path.join(folder, f),
                                  os.path.join(folder, new_stem + f[len(info.stem):])))
        except OSError:
            pass
        for old, new in pairs:
            if new.lower() in targets:
                continue
            if os.path.exists(new):
                try:
                    if not os.path.samefile(old, new):
                        continue
                except OSError:
                    continue
            targets.add(new.lower())
            plan.append((old, new))
    return plan


def rename_log_path():
    return os.path.join(data_dir(), "rename_history.json")


def _read_rename_log():
    try:
        with open(rename_log_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def apply_renames(plan):
    """Rename each (old, new) pair and record the batch so it can be undone.
    Returns the list of pairs actually renamed."""
    done = []
    for old, new in plan:
        try:
            os.rename(old, new)
            done.append([old, new])
        except OSError as e:
            dlog(f"rename failed {old} -> {new}: {e!r}")
    if done:
        hist = _read_rename_log()
        hist.append({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "items": done})
        try:
            with open(rename_log_path(), "w", encoding="utf-8") as f:
                json.dump(hist[-50:], f, indent=1)
        except OSError:
            pass
    return done


def undo_last_rename():
    """Reverse the most recent rename batch. Returns the restored original paths."""
    hist = _read_rename_log()
    restored = []
    while hist and not restored:
        batch = hist.pop()
        for old, new in reversed(batch.get("items", [])):
            if os.path.exists(new) and not os.path.exists(old):
                try:
                    os.rename(new, old)
                    restored.append(old)
                except OSError as e:
                    dlog(f"undo rename failed {new} -> {old}: {e!r}")
    try:
        with open(rename_log_path(), "w", encoding="utf-8") as f:
            json.dump(hist, f, indent=1)
    except OSError:
        pass
    return restored


def norm(text):
    return re.sub(r"[\W_]+", " ", (text or "").lower()).strip()


def episode_in_text(text, info):
    """True / False if text names our / another episode, None if it names none.
    Multi-episode ranges (S01E01E02) count when they overlap the video's episode(s)."""
    m = MULTI_SE_RE.search(text) or ALT_RE.search(text)
    if not m:
        return None
    s, e = int(m.group(1)), int(m.group(2))
    e2 = int(m.group(3)) if (m.re is MULTI_SE_RE and m.group(3)) else e
    if s != info.season:
        return False
    lo, hi = info.episode, info.episode_end or info.episode
    return lo <= e2 and e <= hi


def season_of(text):
    t = norm(text)
    for i, w in enumerate(ORDINALS, 1):
        if re.search(rf"\b{w} season\b", t):
            return i
    m = re.search(r"\bseason (\d{1,2})\b", t) or re.search(r"\bs(\d{1,2})\b", t)
    return int(m.group(1)) if m else None


def title_score(text, query):
    """0..1 fuzzy title match: exact words first, then best of plain ratio,
    word-order-independent ratio and shared-word fraction (tolerates typos,
    reordered words and small extras like a year or edition tag)."""
    t, q = norm(re.sub(r"\(\d{4}\)", " ", text)), norm(query)
    qt = q.split()
    if not qt:
        return 0.0
    tt = t.split()
    if all(w in tt for w in qt):
        return 0.7 + 0.3 * (len(qt) / max(len(tt), 1))
    plain = difflib.SequenceMatcher(None, t, q).ratio()
    sorted_ratio = difflib.SequenceMatcher(None, " ".join(sorted(tt)), " ".join(sorted(qt))).ratio()
    overlap = len(set(qt) & set(tt)) / max(len(set(qt)), 1)
    return 0.7 * max(plain, sorted_ratio, overlap)


# --------------------------------------------------- hash + release matching
def opensubtitles_hash(path):
    """The 64-bit OpenSubtitles movie hash (file size + first/last 64 KB)."""
    size = os.path.getsize(path)
    if size < 131072:
        return None
    h = size
    with open(path, "rb") as f:
        for offset in (0, max(0, size - 65536)):
            f.seek(offset)
            buf = f.read(65536)
            h += sum(struct.unpack("<%dQ" % (len(buf) // 8), buf[: len(buf) // 8 * 8]))
            h &= 0xFFFFFFFFFFFFFFFF
    return "%016x" % h


RES_RE = re.compile(r"(2160p|4k|1080[pi]|720p|576p|480p)", re.I)
SRC_MAP = [("remux", "remux"), ("blu", "bluray"), ("bdrip", "bluray"), ("brrip", "bluray"), ("web", "web"),
           ("hdtv", "hdtv"), ("pdtv", "hdtv"), ("dvd", "dvd"), ("hdrip", "hdrip")]
CODEC_MAP = [("x265", "hevc"), ("h265", "hevc"), ("hevc", "hevc"), ("x264", "h264"), ("h264", "h264"),
             ("avc", "h264"), ("xvid", "xvid"), ("av1", "av1")]
NOT_GROUPS = {"dl", "rip", "ray", "hd", "dts", "aac", "ac3", "ddp", "atmos", "hdr", "sdr", "dv", "multi",
              "sub", "subs", "eng", "srt", "proper", "repack", "internal", "extended", "uncut"}


def release_attrs(text):
    t = re.sub(r"\.(srt|ass|ssa|sub|vtt|zip|rar|mkv|mp4|avi)$", "", (text or "").strip().lower())
    res = RES_RE.search(t)
    res = res.group(1).replace("4k", "2160p").replace("1080i", "1080p") if res else None
    src = next((v for k, v in SRC_MAP if k in t), None)
    codec = next((v for k, v in CODEC_MAP if k in t), None)
    group = None
    m = re.search(r"-([a-z0-9]{2,12})\s*$", t) or re.search(r"^\[([a-z0-9]{2,15})\]", t)
    if m and m.group(1) not in NOT_GROUPS:
        group = m.group(1)
    return {"res": res, "src": src, "codec": codec, "group": group, "edition": edition_of(text)}


REL_WEIGHTS = {"group": 0.35, "src": 0.25, "res": 0.2, "codec": 0.1, "edition": 0.1}


def release_score(rel, stem):
    """0..1 - how well a subtitle's release name fits the video file name.

    Only what the subtitle states is judged: a matching attribute scores full, an attribute the
    video name does not show scores half, a conflicting one scores zero."""
    a, b = release_attrs(rel), release_attrs(stem)
    ratio = difflib.SequenceMatcher(None, norm(rel), norm(stem)).ratio()
    if not any(b.values()):
        return 0.6  # video name carries no release info: nothing to judge by
    stated = [k for k in REL_WEIGHTS if a[k]]
    if not stated:
        return 0.4 + 0.1 * ratio  # unknown subtitle release: neutral, not weak
    total = sum(REL_WEIGHTS[k] for k in stated)
    got = sum(REL_WEIGHTS[k] * (1.0 if a[k] == b[k] else 0.5 if b[k] is None else 0.0) for k in stated)
    return min(0.85 * got / total + 0.15 * ratio, 1.0)


# --------------------------------------------------------------------- HTTP
_cj = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")


def http_request(url, data=None, headers=None, method=None, timeout=40, retries=2):
    h = {"User-Agent": UA, "Accept": "text/html,application/json,application/xhtml+xml,*/*;q=0.8",
         "Accept-Language": "en-US,en;q=0.9"}
    if headers:
        h.update(headers)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=h, method=method)
            with _opener.open(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if (e.code >= 500 or e.code == 429) and attempt < retries:
                wait = 1.5 * (attempt + 1)
                if e.code == 429:  # rate limited: honor the server's Retry-After (capped)
                    try:
                        wait = max(wait, min(int(e.headers.get("Retry-After") or 0), 30))
                    except (TypeError, ValueError):
                        pass
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, OSError):
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise


def http_get(url, timeout=40, headers=None):
    return http_request(url, headers=headers, timeout=timeout)


def decode(data):
    for enc in ("utf-8", "cp1256", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def get_json(url, headers=None):
    return json.loads(decode(http_get(url, headers=headers)))


def friendly_error(e):
    if isinstance(e, urllib.error.HTTPError):
        return {
            401: "HTTP 401: invalid or missing API key / login",
            403: "HTTP 403: blocked or invalid key (the site may use Cloudflare protection)",
            404: "HTTP 404: page not found (check the site address in Settings > Advanced)",
            406: "HTTP 406: daily download limit reached",
            429: "HTTP 429: too many requests - wait a bit",
        }.get(e.code, f"HTTP {e.code}")
    if isinstance(e, urllib.error.URLError):
        return f"network error: {e.reason}"
    if isinstance(e, TimeoutError):
        return "timed out"
    return str(e)


# ================================================== subtitle text handling
TIME_RE = re.compile(r"(?:(\d+):)?(\d\d):(\d\d)[.,](\d{1,3})\s*-->\s*(?:(\d+):)?(\d\d):(\d\d)[.,](\d{1,3})")
SRT_TIME = re.compile(rb"\d\d:\d\d:\d\d[,.]\d{1,3}\s*-->\s*\d\d:\d\d:\d\d")
KEEP_TAGS = re.compile(r"</?(?!(?:i|b|u)\b)[^>]*>")


def _ms(h, m, s, frac):
    return ((int(h or 0) * 60 + int(m)) * 60 + int(s)) * 1000 + int((frac + "00")[:3])


def fmt_ms(ms):
    ms = max(0, int(round(ms)))
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt_vtt(text):
    cues = []
    for block in re.split(r"\r?\n\s*\r?\n", text.strip().lstrip("\ufeff")):
        lines = [l.rstrip() for l in block.splitlines()]
        for i, l in enumerate(lines):
            m = TIME_RE.search(l)
            if m:
                g = m.groups()
                body = [KEEP_TAGS.sub("", x).strip() for x in lines[i + 1:]]
                body = [x for x in body if x]
                if body:
                    cues.append({"start": _ms(g[0], g[1], g[2], g[3]), "end": _ms(g[4], g[5], g[6], g[7]), "lines": body})
                break
    return cues


def _ass_time(t):
    m = re.match(r"\s*(\d+):(\d\d):(\d\d)[.:](\d+)", t)
    if not m:
        return 0
    h, mi, s, frac = m.groups()
    ms = int((frac + "000")[:3]) if len(frac) >= 3 else int(frac.ljust(2, "0")) * 10
    return ((int(h) * 60 + int(mi)) * 60 + int(s)) * 1000 + ms


def parse_ass(text):
    fmt, cues = None, []
    for line in text.splitlines():
        line = line.strip()
        low = line.lower()
        if low.startswith("format:") and "start" in low and "text" in low and fmt is None:
            fmt = [c.strip().lower() for c in line.split(":", 1)[1].split(",")]
        elif low.startswith("dialogue:"):
            f = fmt or ["layer", "start", "end", "style", "name", "marginl", "marginr", "marginv", "effect", "text"]
            parts = line.split(":", 1)[1].lstrip().split(",", len(f) - 1)
            if len(parts) < len(f):
                continue
            d = dict(zip(f, parts))
            txt = re.sub(r"\{[^}]*\}", "", d.get("text", ""))
            txt = txt.replace("\\N", "\n").replace("\\n", "\n").replace("\\h", " ")
            lines = [x.strip() for x in txt.split("\n") if x.strip()]
            if lines:
                cues.append({"start": _ass_time(d.get("start", "")), "end": _ass_time(d.get("end", "")), "lines": lines})
    cues.sort(key=lambda c: c["start"])
    return cues


def parse_subtitle(text, ext=".srt"):
    return parse_ass(text) if ext.lower() in (".ass", ".ssa") else parse_srt_vtt(text)


def write_srt(cues, bom=False):
    out = []
    for i, c in enumerate(cues, 1):
        out.append(f"{i}\r\n{fmt_ms(c['start'])} --> {fmt_ms(c['end'])}\r\n" + "\r\n".join(c["lines"]) + "\r\n")
    data = ("\r\n".join(out)).encode("utf-8")
    return (codecs.BOM_UTF8 + data) if bom else data


# ---- encoding detection -> UTF-8
def _script_ratio(text, lang):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    ranges = {"Arabic": (0x0600, 0x06FF), "Persian": (0x0600, 0x06FF), "Russian": (0x0400, 0x04FF)}
    if lang in ranges:
        lo, hi = ranges[lang]
        return sum(lo <= ord(c) <= hi for c in letters) / len(letters)
    return sum(ord(c) < 0x250 for c in letters) / len(letters)


def decode_bytes(data, lang="English"):
    """Best-effort text from a subtitle file of unknown encoding."""
    if data.startswith(codecs.BOM_UTF8):
        return data[3:].decode("utf-8", "replace")
    if data[:2] in (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE):
        return data.decode("utf-16", "replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    best, best_score = None, -1.0
    for enc in LANGS.get(lang, {}).get("cp", []) + ["cp1252"]:
        try:
            t = data.decode(enc)
        except UnicodeDecodeError:
            continue
        sc = _script_ratio(t, lang)
        if sc > best_score:
            best, best_score = t, sc
    return best if best is not None else data.decode("latin-1")


# ---- cleanup
AD_ANY = re.compile(
    r"opensubtitles|open subtitles|advertise your product|support us and become vip|become a vip member|"
    r"subscene|subf2m|yifysubtitles|yts\.(mx|am|lt)|addic7ed|podnapisi|downloaded from|please rate this subtitle|"
    r"for removing all ads|https?://|www\.[a-z0-9-]+\.[a-z]{2,}", re.I)
AD_CREDIT = re.compile(
    r"(sync(ed|ing)?|resync(ed)?|corrected|translated|subtitles?|captions?|encoded|ripped|timing|edited)\s+"
    r"(and\s+\w+\s+)?(by|&|:)|^\s*(sync|subs?|trans(lation)?)\s*[:-]", re.I)


def remove_ads(cues):
    n, out = len(cues), []
    for i, c in enumerate(cues):
        text = " ".join(c["lines"])
        edge = i < 4 or i >= n - 4
        if AD_ANY.search(text) or (edge and AD_CREDIT.search(text)):
            continue
        out.append(c)
    return out


_HI_BRACKET = re.compile(r"\[[^\]]*\]|\([^)]*\)|\{[^}]*\}")
_HI_SPEAKER = re.compile(r"^\s*-?\s*[A-Z][A-Z0-9 .'#&-]{1,24}:\s+")


def strip_hi(cues):
    out = []
    for c in cues:
        lines = []
        for l in c["lines"]:
            if "\u266a" in l or "\u266b" in l:  # music lines
                continue
            l = _HI_BRACKET.sub("", l)
            l = _HI_SPEAKER.sub("", l).strip()
            if re.fullmatch(r"[-\s.]*", l):
                continue
            lines.append(l)
        if lines:
            if len(c["lines"]) > 1 and len(lines) == 1 and lines[0].startswith("- "):
                lines[0] = lines[0][2:]
            out.append({"start": c["start"], "end": c["end"], "lines": lines})
    return out


def process_subtitle(raw, ext, lang="English", opts=None):
    """Raw subtitle bytes -> (bytes, ext) after the optional fixes. Unknown formats pass through."""
    o = dict(DEFAULT_CLEAN)
    o.update(opts or {})
    ext = ext.lower()
    if ext not in (".srt", ".vtt", ".ass", ".ssa"):
        return raw, ext
    text = decode_bytes(raw, lang)
    convert = ext != ".srt" and o["to_srt"]
    clean = o["ads"] or o["hi"]
    if not convert and not clean:
        if not o["utf8"]:
            return raw, ext
        data = text.encode("utf-8")
        return (codecs.BOM_UTF8 + data if o["bom"] else data), ext
    cues = parse_subtitle(text, ext)
    if not cues:
        return (text.encode("utf-8") if o["utf8"] else raw), ext
    if o["ads"]:
        cues = remove_ads(cues)
    if o["hi"]:
        cues = strip_hi(cues)
    return write_srt(cues, o["bom"]), ".srt"


# ---- timing tools
def shift_cues(cues, ms):
    return [{"start": max(0, c["start"] + ms), "end": max(0, c["end"] + ms), "lines": c["lines"]} for c in cues]


def scale_fps(cues, fps_from, fps_to):
    """Timing written for a video at fps_from, retimed for a video at fps_to."""
    k = float(fps_from) / float(fps_to)
    return [{"start": c["start"] * k, "end": c["end"] * k, "lines": c["lines"]} for c in cues]


def transform_file(path, shift_ms=0, fps_from=None, fps_to=None, lang="English", opts=None, overwrite=False):
    """Retime / convert a subtitle file. Returns (output_path, message)."""
    with open(path, "rb") as f:
        raw = f.read()
    ext = os.path.splitext(path)[1].lower()
    cues = parse_subtitle(decode_bytes(raw, lang), ext)
    if not cues:
        raise RuntimeError("no subtitle cues found in this file")
    if fps_from and fps_to and float(fps_from) != float(fps_to):
        cues = scale_fps(cues, fps_from, fps_to)
    if shift_ms:
        cues = shift_cues(cues, int(shift_ms))
    o = dict(DEFAULT_CLEAN)
    o.update(opts or {})
    if o["ads"]:
        cues = remove_ads(cues)
    if o["hi"]:
        cues = strip_hi(cues)
    base = os.path.splitext(path)[0]
    out = base + ".srt" if overwrite else base + ".fixed.srt"
    if overwrite and os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    with open(out, "wb") as f:
        f.write(write_srt(cues, o["bom"]))
    return out, f"Saved {os.path.basename(out)} ({len(cues)} cues)" + (" - original kept as .bak" if overwrite else "")


# ======================================================== archives / 7-Zip
def find_7z(custom=""):
    cands = [custom, os.path.join(app_dir(), "7zip", "7z.exe"),
             os.path.join(getattr(sys, "_MEIPASS", ""), "7zip", "7z.exe"),
             os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "7-Zip", "7z.exe"),
             os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "7-Zip", "7z.exe"),
             shutil.which("7z") or "", shutil.which("7za") or "", shutil.which("7zz") or ""]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def extract_with_7z(data, exe):
    with tempfile.TemporaryDirectory() as tmp:
        arc = os.path.join(tmp, "a.bin")
        with open(arc, "wb") as f:
            f.write(data)
        out = os.path.join(tmp, "out")
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        r = subprocess.run([exe, "x", "-y", "-o" + out, arc], capture_output=True, timeout=180, creationflags=flags)
        if r.returncode not in (0, 1):
            raise RuntimeError("7-Zip could not unpack the archive")
        files = {}
        for root, _d, names in os.walk(out):
            for n in names:
                if n.lower().endswith(SUB_EXT):
                    with open(os.path.join(root, n), "rb") as f:
                        files[n] = f.read()
        return files


def archive_files(data, sevenzip=None):
    """Subtitle files inside a download: {name: bytes}. Handles zip, rar/7z (needs 7-Zip) and bare files."""
    if data[:2] == b"PK":
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            return {}
        return {n: zf.read(n) for n in zf.namelist() if n.lower().endswith(SUB_EXT) and not n.endswith("/")}
    if data[:4] == b"Rar!" or data[:6] == b"7z\xbc\xaf\x27\x1c":
        if not sevenzip:
            raise RuntimeError("RAR/7z archive: install 7-Zip or set its path in Settings > Archives")
        return extract_with_7z(data, sevenzip)
    head = data[:3000]
    if SRT_TIME.search(head):
        return {"subtitle.vtt" if head.lstrip(b"\xef\xbb\xbf").startswith(b"WEBVTT") else "subtitle.srt": data}
    if b"[Script Info]" in head or b"[V4+ Styles]" in head:
        return {"subtitle.ass": data}
    return {}


def looks_like_file(data):
    head = data[:3000]
    return (head[:2] == b"PK" or head[:4] == b"Rar!" or head[:6] == b"7z\xbc\xaf\x27\x1c"
            or bool(SRT_TIME.search(head)) or b"[Script Info]" in head)


def kind_ext(data):
    if data[:2] == b"PK":
        return ".zip"
    if data[:4] == b"Rar!":
        return ".rar"
    if data[:6] == b"7z\xbc\xaf\x27\x1c":
        return ".7z"
    return ".srt"


def choose_file(files, info):
    """Pick the right subtitle for this video out of {name: bytes}. Returns (name, bytes) or None."""
    names = list(files)
    if not names:
        return None
    if info.is_episode:
        matches = [n for n in names if episode_in_text(os.path.basename(n), info)]
        if matches:
            names = matches
        elif len(names) > 1:
            return None  # season pack without our episode
    names.sort(key=lambda n: (not n.lower().endswith(".srt"), -len(files[n])))
    return names[0], files[names[0]]


def save_blob(data, name_hint, dest, lang="English", opts=None, extract=True, sevenzip=None):
    """Save a download into dest (Search page). Returns a message."""
    os.makedirs(dest, exist_ok=True)
    safe = re.sub(r'[<>:"/\\|?*]+', "_", name_hint or "subtitle").strip()[:120] or "subtitle"

    def unique(path):
        base, ext = os.path.splitext(path)
        n, p = 1, path
        while os.path.exists(p):
            n += 1
            p = f"{base} ({n}){ext}"
        return p

    arch = kind_ext(data) != ".srt"
    if (not arch) or extract:
        try:
            files = archive_files(data, sevenzip)
        except RuntimeError as e:
            files, note = {}, str(e)
        else:
            note = ""
        saved = []
        for n, raw in files.items():
            body, ext = process_subtitle(raw, os.path.splitext(n)[1] or ".srt", lang, opts)
            stem = os.path.splitext(os.path.basename(n))[0]
            if stem == "subtitle":
                stem = os.path.splitext(safe)[0]
            p = unique(os.path.join(dest, stem + ext))
            with open(p, "wb") as f:
                f.write(body)
            saved.append(os.path.basename(p))
        if saved:
            return "Saved: " + ", ".join(saved[:3]) + (f" (+{len(saved) - 3} more)" if len(saved) > 3 else "")
        if note:
            p = unique(os.path.join(dest, os.path.splitext(safe)[0] + kind_ext(data)))
            with open(p, "wb") as f:
                f.write(data)
            return f"Saved archive {os.path.basename(p)} - {note}"
    p = unique(os.path.join(dest, os.path.splitext(safe)[0] + kind_ext(data)))
    with open(p, "wb") as f:
        f.write(data)
    return "Saved: " + os.path.basename(p)


def preview_text(data, name_hint, lang="English", opts=None, sevenzip=None, max_cues=60):
    files = archive_files(data, sevenzip)
    if not files:
        raise RuntimeError("no readable subtitle inside this download")
    name = next(iter(files))
    body, ext = process_subtitle(files[name], os.path.splitext(name)[1], lang, opts)
    cues = parse_subtitle(decode_bytes(body, lang), ext)
    lines = [f"{fmt_ms(c['start'])}   " + " / ".join(c["lines"]) for c in cues[:max_cues]]
    head = f"{os.path.basename(name)}  -  {len(cues)} cues  ({ext}, UTF-8)\n" + "-" * 60 + "\n"
    return head + "\n".join(lines) + ("\n..." if len(cues) > max_cues else "")


# ================================================================== sources
def as_list(data, *keys):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in keys + ("data", "results", "items", "subtitles", "movies"):
            v = data.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                r = as_list(v, *keys)
                if r:
                    return r
    return []


def pick(d, *names, default=None):
    for n in names:
        if isinstance(d, dict) and d.get(n) not in (None, ""):
            return d[n]
    return default


def imdb_suggest(q):
    """IMDb's public suggestion endpoint: title, year, type, cast, poster url."""
    q = (q or "").strip().lower()
    if not q:
        return []
    first = q[0] if q[0].isalnum() else "x"
    url = "https://v2.sg.media-imdb.com/suggestion/%s/%s.json" % (first, urllib.parse.quote(q.replace(" ", "_")))
    out = []
    for d in get_json(url).get("d", []):
        if str(d.get("id", "")).startswith("tt"):
            img = d.get("i") or {}
            out.append({"id": d["id"], "title": d.get("l", ""), "year": d.get("y"),
                        "type": d.get("q") or d.get("qid") or "", "cast": d.get("s", ""),
                        "poster": img.get("imageUrl") if isinstance(img, dict) else None})
    return out


def imdb_title(tt):
    try:
        res = imdb_suggest(tt)
    except Exception as e:
        dlog(f"imdb lookup failed: {e}")
        return None
    for r in res:
        if r["id"].lower() == tt.lower():
            return r["title"]
    return res[0]["title"] if res else None


def imdb_details(title, year=None):
    """Best IMDb match for a result title (poster, cast...). None if nothing fits."""
    base = re.sub(r"\(.*?\)|-?\s*\b\w+ season\b|-?\s*\bseason \d+\b", " ", title, flags=re.I).strip()
    best, best_s = None, 0.0
    for r in imdb_suggest(base):
        s = title_score(r["title"], base)
        if year and str(r.get("year")) == str(year):
            s += 0.3
        if s > best_s:
            best, best_s = r, s
    return best if best_s >= 0.6 else None


# ---- SubSource (official API, free key)
class SubSourceSource:
    name = "SubSource"
    movies_only = False

    def __init__(self, key, delay=0.6):
        self.key, self.delay = key, delay
        self.hdr = {"X-API-Key": key or ""}
        self.cache = {}
        self.list_style = None

    def configured(self):
        return bool(self.key)

    def _get(self, path, **params):
        if not self.key:
            raise RuntimeError("Add your SubSource API key in Settings > Sources (subsource.net -> Profile -> API Key)")
        url = f"{SS_BASE}/{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        if url in self.cache:
            return self.cache[url]
        time.sleep(self.delay)
        data = get_json(url, headers=self.hdr)
        self.cache[url] = data
        return data

    def search(self, query):
        kind = "imdb" if IMDB_RE.match(query.strip()) else "text"
        out = []
        for m in as_list(self._get("movies/search", searchType=kind, q=query.strip()), "movies"):
            title = pick(m, "title", "name", default="")
            mid = pick(m, "movieId", "id", "movie_id")
            if mid is None or not title:
                continue
            year = pick(m, "releaseYear", "year", default=None)
            season = pick(m, "season", "seasonNumber", default=None)
            label = title + (f" ({year})" if year else "") + (f" - Season {season}" if season else "")
            try:
                season = int(season) if season is not None else None
            except ValueError:
                season = None
            out.append({"title": label, "id": mid, "source": self.name,
                        "kind": str(pick(m, "type", "mediaType", default="")).lower(),
                        "season": season, "year": year})
        return out

    def subs(self, item, lang):
        L = LANGS.get(lang, LANGS["English"])["ss"]
        mid = item["id"]
        variants = [("subtitles", {"movieId": mid, "language": L}),
                    ("subtitles", {"movie_id": mid, "language": L}),
                    (f"movies/{mid}/subtitles", {"language": L})]
        if self.list_style is not None:
            variants = [variants[self.list_style]]
        raw, last = [], None
        for i, (path, params) in enumerate(variants):
            try:
                raw = as_list(self._get(path, **params), "subtitles")
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 429):
                    raise
                last = e
                continue
            if self.list_style is None:
                self.list_style = i
            last = None
            break
        if last:
            raise last
        out = []
        for s in raw:
            sid = pick(s, "subtitleId", "id", "subtitle_id")
            if sid is None:
                continue
            rel = pick(s, "releaseInfo", "release_info", "releaseName", "release", "name", default="")
            if isinstance(rel, list):
                rel = " / ".join(str(x) for x in rel)
            out.append({"release": str(rel), "lang": lang, "author": str(pick(s, "author", "uploader", "user", default="") or ""),
                        "id": sid, "hi": bool(pick(s, "hearingImpaired", "hearing_impaired", "hi", default=False))})
        return out

    def fetch(self, sub):
        time.sleep(self.delay)
        data = http_get(f"{SS_BASE}/subtitles/{sub['id']}/download", timeout=60, headers=self.hdr)
        return sub.get("release") or "subtitle", data


# ---- OpenSubtitles.com REST API (API key + account; supports file-hash matching)
class OpenSubtitlesSource:
    name = "OpenSubtitles"
    movies_only = False
    supports_hash = True

    def __init__(self, key, user="", password=""):
        self.key, self.user, self.pw = key, user, password
        self.base, self.token = OS_BASE, None

    def configured(self):
        return bool(self.key)

    def _h(self, auth=False):
        h = {"Api-Key": self.key or "", "User-Agent": f"SubGrab v{VERSION}", "Accept": "application/json",
             "Content-Type": "application/json"}
        if auth and self.token:
            h["Authorization"] = "Bearer " + self.token
        return h

    def _get(self, path, **params):
        if not self.key:
            raise RuntimeError("Add your OpenSubtitles API key in Settings > Sources")
        params = {k: v for k, v in params.items() if v not in (None, "")}
        url = f"{self.base}/{path}" + ("?" + urllib.parse.urlencode(sorted((k, str(v)) for k, v in params.items())) if params else "")
        time.sleep(0.3)
        return json.loads(decode(http_request(url, headers=self._h())))

    def login(self):
        if self.token:
            return
        if not (self.user and self.pw):
            raise RuntimeError("OpenSubtitles downloads need your username and password (Settings > Sources)")
        body = json.dumps({"username": self.user, "password": self.pw}).encode()
        data = json.loads(decode(http_request(f"{self.base}/login", data=body, headers=self._h(), method="POST")))
        self.token = data.get("token")
        if not self.token:
            raise RuntimeError("OpenSubtitles login failed")
        if data.get("base_url"):
            self.base = "https://" + str(data["base_url"]).replace("https://", "").rstrip("/") + "/api/v1"

    def search(self, query):
        q = query.strip()
        if IMDB_RE.match(q):
            return [{"title": imdb_title(q) or q, "id": int(q[2:]), "source": self.name, "kind": "movie", "year": None}]
        out = []
        for f in as_list(self._get("features", query=q), "features"):
            a = f.get("attributes", f) if isinstance(f, dict) else {}
            title, imdb = pick(a, "title", "original_title", default=""), pick(a, "imdb_id")
            if not title or not imdb:
                continue
            year = pick(a, "year")
            ftype = str(pick(a, "feature_type", default="")).lower()
            out.append({"title": title + (f" ({year})" if year else ""), "id": imdb, "source": self.name,
                        "kind": "series" if ("tv" in ftype or "episode" in ftype) else "movie", "year": year})
        return out

    @staticmethod
    def _cand(row):
        a = row.get("attributes", row)
        files = a.get("files") or [{}]
        fid = pick(files[0], "file_id")
        if fid is None:
            return None
        fd = a.get("feature_details") or {}
        return {"id": fid, "release": str(pick(a, "release", default="") or pick(files[0], "file_name", default="")),
                "season": pick(fd, "season_number"), "episode": pick(fd, "episode_number"),
                "hi": bool(a.get("hearing_impaired")), "hash": bool(a.get("moviehash_match")),
                "author": str((a.get("uploader") or {}).get("name", "")), "downloads": a.get("download_count", 0)}

    def subs(self, item, lang):
        L = LANGS.get(lang, LANGS["English"])["suffix"]
        key = "parent_imdb_id" if item.get("kind") == "series" else "imdb_id"
        out = []
        for row in as_list(self._get("subtitles", languages=L, **{key: item["id"]}), "subtitles"):
            c = self._cand(row)
            if c:
                tag = f"S{int(c['season']):02d}E{int(c['episode']):02d}  " if c["season"] and c["episode"] else ""
                out.append({"release": tag + c["release"], "lang": lang, "author": c["author"], "id": c["id"], "hi": c["hi"]})
        return out

    def auto_candidates(self, info, lang, moviehash=None):
        L = LANGS.get(lang, LANGS["English"])["suffix"]
        searches = []
        if moviehash:
            searches.append(dict(languages=L, moviehash=moviehash))
        q = dict(languages=L, query=info.title)
        if info.is_episode:
            q.update(type="episode", season_number=info.season, episode_number=info.episode)
        else:
            q.update(type="movie", year=info.year)
        searches.append(q)
        for params in searches:
            cands = []
            for row in as_list(self._get("subtitles", **params), "subtitles"):
                c = self._cand(row)
                if not c:
                    continue
                cands.append({"key": str(c["id"]), "release_name": c["release"], "hash": c["hash"], "hi": c["hi"],
                              "season": c["season"], "episode": c["episode"],
                              "sub": {"id": c["id"], "release": c["release"]}})
            yield cands

    def fetch(self, sub):
        self.login()
        body = json.dumps({"file_id": int(sub["id"]), "sub_format": "srt"}).encode()
        info = json.loads(decode(http_request(f"{self.base}/download", data=body, headers=self._h(True), method="POST")))
        link = info.get("link")
        if not link:
            raise RuntimeError(info.get("message") or "OpenSubtitles gave no download link")
        return info.get("file_name") or sub.get("release") or "subtitle", http_get(link, timeout=60)


# ---- generic scraper for subtitle search sites
A_TAG = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.I | re.S)
HREF_RE = re.compile(r"""href\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
ID_RE = re.compile(r"""\bid\s*=\s*["']([^"']*)["']""", re.I)
TAGS_RE = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.I | re.S)
BLOCK_SPLIT = re.compile(r"(?i)(?=<(?:tr|li|article)\b)")
SKIP_PATH = re.compile(r"/(search|login|register|signin|signup|tag|tags|category|categories|page|wp-|feed|"
                       r"author|contact|about|dmca|privacy|terms|faq|rss|upload|forum|user)\b", re.I)
ALL_LANG_WORDS = sorted({w for v in LANGS.values() for w in v["words"]} |
                        {"hebrew", "greek", "polish", "swedish", "danish", "norwegian", "finnish", "korean",
                         "japanese", "chinese", "vietnamese", "thai", "romanian", "czech", "hungarian",
                         "bulgarian", "serbian", "croatian", "malay", "urdu", "bengali"})


def strip_tags(t):
    return re.sub(r"\s+", " ", htmllib.unescape(TAGS_RE.sub(" ", t))).strip()


def find_anchors(page, base):
    out = []
    for m in A_TAG.finditer(page):
        attrs, inner = m.group(1), m.group(2)
        hm = HREF_RE.search(attrs)
        if not hm:
            continue
        href = (hm.group(1) or hm.group(2) or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        im = ID_RE.search(attrs)
        out.append({"href": urllib.parse.urljoin(base, htmllib.unescape(href)),
                    "text": strip_tags(inner), "id": im.group(1) if im else ""})
    return out


def find_blocks(page, base):
    res = []
    for chunk in BLOCK_SPLIT.split(page):
        a = find_anchors(chunk, base)
        if a:
            res.append({"text": strip_tags(chunk)[:400], "anchors": a})
    return res


def host_of(url):
    return urllib.parse.urlparse(url).netloc.lower().replace("www.", "")


class WebSource:
    def __init__(self, name, base, templates, movies_only=False, delay=0.6):
        self.name, self.base, self.templates = name, base.rstrip("/"), templates
        self.movies_only, self.delay = movies_only, delay
        self._lang_name = "English"

    def configured(self):
        return True

    def get(self, url, referer=None):
        time.sleep(self.delay)
        data = http_get(url, headers={"Referer": referer or self.base + "/"})
        dlog(f"GET {url} -> {len(data)} bytes")
        return data

    def search(self, query):
        q = query.strip()
        if IMDB_RE.match(q):
            q = imdb_title(q) or q
        results, seen, last_err, ok_any = [], set(), None, False
        host = host_of(self.base)
        for tpl in self.templates:
            url = self.base + tpl.format(q=urllib.parse.quote_plus(q))
            try:
                page = decode(self.get(url))
                ok_any = True
            except Exception as e:
                last_err = e
                dlog(f"{self.name} search failed {url}: {e}")
                continue
            for a in find_anchors(page, url):
                if host_of(a["href"]) != host:
                    continue
                path = urllib.parse.urlparse(a["href"]).path
                if len(path) < 2 or SKIP_PATH.search(path):
                    continue
                txt = a["text"]
                if not (2 <= len(txt) <= 140):
                    continue
                sc = title_score(txt, q)
                if sc < 0.5:
                    continue
                key = a["href"].split("#")[0]
                if key in seen:
                    continue
                seen.add(key)
                results.append({"title": txt, "url": key, "source": self.name, "score": sc})
            dlog(f"{self.name} search {url}: {len(results)} results")
            if results:
                break
        if not results and not ok_any and last_err:
            raise last_err
        results.sort(key=lambda r: -r["score"])
        return results[:40]

    def subs(self, item, lang):
        L = LANGS.get(lang, LANGS["English"])
        self._lang_name = lang
        url = item["url"]
        path = urllib.parse.urlparse(url).path
        entries = self._entries(decode(self.get(url, referer=self.base)), url, L, True, path)
        if not entries:
            for slug in dict.fromkeys([L["slug"], L["ss"], L["suffix"]]):
                u = url.rstrip("/") + "/" + slug
                try:
                    page = decode(self.get(u, referer=url))
                except Exception as e:
                    dlog(f"{self.name} language page failed {u}: {e}")
                    continue
                entries = self._entries(page, u, L, False, path)
                if entries:
                    break
        dlog(f"{self.name} subs {url}: {len(entries)} entries")
        return entries

    def _entries(self, page, page_url, L, filter_lang, base_path):
        base_path = (base_path or "").rstrip("/")
        host = host_of(self.base)
        lang_slugs = ({v["slug"] for v in LANGS.values()} | {v["ss"] for v in LANGS.values()}
                      | {v["suffix"] for v in LANGS.values()})
        found, seen = [], set()
        for b in find_blocks(page, page_url):
            for a in b["anchors"]:
                path = urllib.parse.urlparse(a["href"]).path
                is_file = path.lower().endswith(ARCHIVE_EXT)
                if not is_file and host_of(a["href"]) != host:
                    continue
                tail = path.rstrip("/").split("/")[-1]
                deeper = bool(base_path) and path.startswith(base_path + "/") and tail not in lang_slugs
                subtitle_like = "/subtitle" in path and re.search(r"\d{3,}", path)
                if not (is_file or deeper or subtitle_like):
                    continue
                if SKIP_PATH.search(path) and not is_file:
                    continue
                key = a["href"].split("#")[0]
                if key in seen:
                    continue
                seen.add(key)
                label = a["text"] if len(a["text"]) >= 8 else b["text"]
                low = (b["text"] + " " + a["text"]).lower()
                found.append({"release": label[:200], "lang": "", "author": "", "url": key,
                              "_hit": any(w in low for w in L["words"]),
                              "_any": any(w in low for w in ALL_LANG_WORDS)})
        if filter_lang and any(e["_any"] for e in found):
            found = [e for e in found if e["_hit"]]
        out = []
        for e in found[:200]:
            e["lang"] = self._lang_name if e["_hit"] else ""
            out.append({k: v for k, v in e.items() if not k.startswith("_")})
        return out

    def fetch(self, sub):
        url, referer = sub["url"], None
        for _hop in range(4):
            data = self.get(url, referer=referer)
            if looks_like_file(data):
                return sub.get("release") or "subtitle", data
            link = self._download_link(decode(data), url)
            if not link or link == url:
                break
            referer, url = url, link
        raise RuntimeError("could not find the download link on the subtitle page")

    @staticmethod
    def _download_link(page, url):
        best, best_s = None, 0
        for a in find_anchors(page, url):
            h, t, i = a["href"].lower(), a["text"].lower(), a["id"].lower()
            s = 0
            if "download" in i:
                s += 5
            if h.split("?")[0].endswith(ARCHIVE_EXT):
                s += 4
            if "download" in h:
                s += 3
            if t.startswith("download"):
                s += 2
            if s > best_s:
                best, best_s = a["href"], s
        return best


def test_source(src):
    """(ok, message) for the Settings 'Test' buttons."""
    if hasattr(src, "configured") and not src.configured():
        return False, "not configured - add your key in Settings"
    t0 = time.time()
    try:
        items = src.search("Inception")
    except Exception as e:
        return False, friendly_error(e)
    ms = int((time.time() - t0) * 1000)
    if not items:
        return False, "reachable, but no results (site may have changed or blocked the request)"
    extra = ""
    if getattr(src, "name", "") == "OpenSubtitles" and src.user and src.pw:
        try:
            src.login()
            extra = ", login OK"
        except Exception as e:
            return False, "search works but login failed: " + friendly_error(e)
    return True, f"OK - {len(items)} results in {ms} ms{extra}"


# ---- update check
def ver_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def check_update():
    """(version, url) of a newer GitHub release, or None."""
    if "YOUR-USERNAME" in GITHUB_REPO:
        return None
    try:
        data = get_json(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", headers={"Accept": "application/vnd.github+json"})
    except Exception:
        # private repo or offline: fall back to the releases page
        return None
    tag = str(data.get("tag_name", "")).lstrip("vV")
    if tag and ver_tuple(tag) > ver_tuple(VERSION):
        return tag, data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest"
    return None


ATTR_NAMES = {"group": "release group", "src": "source", "res": "resolution", "codec": "codec",
              "edition": "edition"}


def match_reason(cand, info):
    """Short human-readable explanation of why a candidate fits the video (or not)."""
    if cand.get("hash"):
        return "file hash: exact match, perfectly in sync"
    a, b = release_attrs(cand.get("release_name", "")), release_attrs(info.stem)
    hits = [k for k in REL_WEIGHTS if a[k] and a[k] == b[k]]
    misses = [k for k in REL_WEIGHTS if a[k] and b[k] and a[k] != b[k]]
    base = "good match" if cand.get("quality", 0) >= WEAK else "weak match"
    parts = []
    if info.is_episode and cand.get("season") == info.season and cand.get("episode") == info.episode:
        parts.append("exact episode")
    if hits:
        parts.append("same " + ", ".join(ATTR_NAMES[k] for k in hits))
    if misses:
        parts.append("different " + ", ".join(ATTR_NAMES[k] for k in misses))
    if not parts and not any(a.values()):
        parts.append("release name carries no details to compare")
    return base + ((" - " + "; ".join(parts)) if parts else "")


# ================================================== automatic folder matching
def rank_items(items, info):
    ranked = []
    for it in items:
        t = it["title"]
        base = re.sub(r"\(.*?\)|-?\s*\b\w+ season\b|-?\s*\bseason \d+\b", " ", t, flags=re.I)
        s = title_score(base, info.title)
        if s < 0.6:
            continue
        ss = it.get("season") or season_of(t)
        if info.is_episode:
            if ss is not None:
                if ss != info.season:
                    continue
                s += 0.3
            elif it.get("kind") in ("series", "tv", "show", "tvseries"):
                s += 0.2
        else:
            if ss is not None:
                s -= 0.3
            y = it.get("year")
            if y is None:
                ym = YEAR_RE.search(t)
                y = int(ym.group(1)) if ym else None
            if info.year and str(y) == str(info.year):
                s += 0.3
        ranked.append((s, it))
    ranked.sort(key=lambda x: -x[0])
    return [it for _s, it in ranked[:3]]


class AutoAdapter:
    """Lets any source be used by the folder auto-downloader."""

    def __init__(self, source, lang):
        self.source, self.lang, self.name = source, lang, source.name
        self.supports_hash = bool(getattr(source, "supports_hash", False))

    def candidate_lists(self, info, moviehash=None):
        if getattr(self.source, "movies_only", False) and info.is_episode:
            return
        if hasattr(self.source, "auto_candidates"):
            for lst in self.source.auto_candidates(info, self.lang, moviehash):
                yield lst
            return
        items = rank_items(self.source.search(info.title), info)
        dlog(f"auto {self.name}: '{info.title}' -> {len(items)} title match(es)")
        for it in items:
            out = []
            for s in self.source.subs(it, self.lang):
                rel = s.get("release", "")
                season = episode = None
                if info.is_episode:
                    ok = episode_in_text(rel, info)
                    if ok is False:
                        continue
                    if ok:
                        season, episode = info.season, info.episode
                out.append({"key": str(s.get("id") or s.get("url")), "release_name": rel, "season": season,
                            "episode": episode, "hi": s.get("hi"), "hash": False, "sub": s})
            yield out

    def download(self, cand):
        return self.source.fetch(cand["sub"])[1]


class Downloader:
    """Finds, ranks and saves the subtitle for one video. Returns (code, text) with
    code in: ok, review (weak match), none, error, skip."""

    def __init__(self, providers, lang, log=None, opts=None, sevenzip=None, weak_save=False, use_hash=True):
        self.providers, self.lang = providers, lang
        self.suffix = LANGS[lang]["suffix"]
        self.log = log or (lambda m: None)
        self.opts, self.sevenzip = dict(DEFAULT_CLEAN, **(opts or {})), sevenzip
        self.weak_save, self.use_hash = weak_save, use_hash
        self.cache, self.dead, self.rar_skipped = {}, set(), False
        self.stats = {p.name: {"ok": 0, "fail": 0, "err": ""} for p in providers}

    # -- helpers
    def _blob(self, prov, cand):
        k = (prov.name, cand["key"])
        if k not in self.cache:
            self.cache[k] = prov.download(cand)
        return self.cache[k]

    def _prepare(self, subs, info):
        for s in subs:
            q = release_score(s.get("release_name", ""), info.stem)
            exact = info.is_episode and s.get("episode") == info.episode and s.get("season") == info.season
            s["quality"] = q
            s["score"] = q + (10 if s.get("hash") else 0) + (0.5 if exact else 0) - (0.05 if s.get("hi") else 0)
            s["reason"] = match_reason(s, info)
        subs.sort(key=lambda s: -s["score"])

    def _hash_for(self, info):
        if self.use_hash and any(getattr(p, "supports_hash", False) for p in self.providers):
            return info.moviehash
        return None

    def write(self, info, data, ext):
        body, out_ext = process_subtitle(data, ext, self.lang, self.opts)
        out = f"{os.path.splitext(info.path)[0]}.{self.suffix}{out_ext}"
        with open(out, "wb") as f:
            f.write(body)
        return out

    @staticmethod
    def _filter(subs, info):
        if not info.is_episode:
            return subs

        def num(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
        eps = {None, 0} | set(range(info.episode, (info.episode_end or info.episode) + 1))
        return [s for s in subs if num(s.get("season")) in (None, 0, info.season)
                and num(s.get("episode")) in eps]

    # -- one provider
    def _try(self, prov, info, mh):
        tried, weak = set(), None
        for subs in prov.candidate_lists(info, mh):
            subs = self._filter([s for s in subs if s["key"] not in tried], info)
            self._prepare(subs, info)
            for sub in subs[:5]:
                tried.add(sub["key"])
                try:
                    files = archive_files(self._blob(prov, sub), self.sevenzip)
                except urllib.error.HTTPError as e:
                    if e.code in (401, 403, 406, 429):
                        raise
                    continue
                except RuntimeError as e:
                    self.rar_skipped = self.rar_skipped or "RAR/7z" in str(e)
                    dlog(f"{prov.name} download problem: {e}")
                    continue
                except (urllib.error.URLError, OSError) as e:
                    dlog(f"{prov.name} download failed: {e}")
                    continue
                picked = choose_file(files, info)
                if not picked:
                    continue
                res = {"data": picked[1], "ext": os.path.splitext(picked[0])[1] or ".srt", "sub": sub, "prov": prov}
                if sub.get("hash") or sub["quality"] >= WEAK:
                    return "good", res
                if weak is None or sub["score"] > weak["sub"]["score"]:
                    weak = res
        return ("weak", weak) if weak else (None, None)

    # -- one video
    def fetch_for(self, info, overwrite=False):
        if not overwrite and existing_sub(info.path, self.suffix):
            return "skip", "skipped (already has subtitle)"
        mh = self._hash_for(info)
        errors, weak_best = [], None
        for prov in self.providers:
            if prov.name in self.dead:
                continue
            try:
                kind, res = self._try(prov, info, mh)
            except urllib.error.HTTPError as e:
                self.stats[prov.name]["fail"] += 1
                self.stats[prov.name]["err"] = friendly_error(e)
                if e.code == 401 or (e.code == 403 and prov.name in KEY_SOURCES):
                    self.dead.add(prov.name)
                    self.log(f"{prov.name}: key/login rejected")
                errors.append(f"{prov.name}: {friendly_error(e)}")
                continue
            except Exception as e:
                dlog(f"{prov.name} error: {e!r}")
                self.stats[prov.name]["fail"] += 1
                self.stats[prov.name]["err"] = friendly_error(e)
                errors.append(f"{prov.name}: {friendly_error(e)}")
                continue
            if kind == "good":
                out = self.write(info, res["data"], res["ext"])
                self.stats[prov.name]["ok"] += 1
                tag = " (hash match)" if res["sub"].get("hash") else ""
                return "ok", f"OK [{prov.name}]{tag}  ->  " + os.path.basename(out)
            if kind == "weak" and (weak_best is None or res["sub"]["score"] > weak_best["sub"]["score"]):
                weak_best = res
        if weak_best:
            if self.weak_save:
                out = self.write(info, weak_best["data"], weak_best["ext"])
                self.stats[weak_best["prov"].name]["ok"] += 1
                return "ok", f"OK [{weak_best['prov'].name}] weak match  ->  " + os.path.basename(out)
            return "review", f"weak match [{weak_best['prov'].name}] - double-click to review"
        live = [p for p in self.providers if p.name not in self.dead]
        if not live:
            return "error", "error: no valid API key / login"
        if errors and len(errors) >= len(live):
            return "error", "error: " + "; ".join(errors)
        note = " (a RAR/7z result was skipped - set up 7-Zip in Settings)" if self.rar_skipped else ""
        return "none", "not found" + note

    # -- manual picking
    def list_candidates(self, info):
        items, errs, seen = [], [], set()
        mh = self._hash_for(info)
        for prov in self.providers:
            try:
                for subs in prov.candidate_lists(info, mh):
                    subs = self._filter(subs, info)
                    self._prepare(subs, info)
                    for s in subs[:10]:
                        if (prov.name, s["key"]) not in seen:
                            seen.add((prov.name, s["key"]))
                            items.append({"prov": prov, "cand": s})
            except Exception as e:
                dlog(f"{prov.name} list error: {e!r}")
                errs.append(f"{prov.name}: {friendly_error(e)}")
        items.sort(key=lambda x: -x["cand"]["score"])
        return items, errs

    def fetch_item(self, info, item):
        files = archive_files(self._blob(item["prov"], item["cand"]), self.sevenzip)
        picked = choose_file(files, info)
        if not picked:
            raise RuntimeError("no matching subtitle inside this download")
        return picked[1], os.path.splitext(picked[0])[1] or ".srt"

    def save_item(self, info, item):
        data, ext = self.fetch_item(info, item)
        return self.write(info, data, ext)

    def preview_item(self, info, item):
        data, ext = self.fetch_item(info, item)
        body, out_ext = process_subtitle(data, ext, self.lang, self.opts)
        cues = parse_subtitle(decode_bytes(body, self.lang), out_ext)
        rows = [f"{fmt_ms(c['start'])}   " + " / ".join(c["lines"]) for c in cues[:80]]
        return f"{len(cues)} cues  |  {item['prov'].name}  |  {item['cand'].get('release_name', '')}\n" + "-" * 60 + "\n" + "\n".join(rows)

    def stats_text(self):
        parts = []
        for n, s in self.stats.items():
            if s["ok"] or s["fail"]:
                parts.append(f"{n} \u2713{s['ok']}" + (f" \u2717{s['fail']} ({s['err']})" if s["fail"] else ""))
        return "  \u00b7  ".join(parts)


def build_sources(cfg):
    """All source objects from saved settings."""
    sites = cfg.get("sites", {})
    src = {}
    for name, (base, tpls, movies_only) in SITES.items():
        src[name] = WebSource(name, sites.get(name) or base, tpls, movies_only)
    src["SubSource"] = SubSourceSource(get_secret(cfg, "subsource_key"))
    src["OpenSubtitles"] = OpenSubtitlesSource(get_secret(cfg, "os_key"), cfg.get("os_user", ""), get_secret(cfg, "os_pass"))
    return src


def ordered_sources(cfg):
    """Source names in the user's priority order."""
    order = [n for n in cfg.get("order", []) if n in SOURCE_ORDER]
    order += [n for n in SOURCE_ORDER if n not in order]
    return order


def enabled_sources(cfg):
    on = cfg.get("enabled")
    on = set(DEFAULT_ENABLED if on is None else [n for n, v in on.items() if v] if isinstance(on, dict) else on)
    return [n for n in ordered_sources(cfg) if n in on]
