# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) - versions follow [SemVer](https://semver.org/).

## [1.0.0] - 2026-11-25

First stable release.

### Added
- Modern Qt (PySide6) interface: Auto Folder, Search, Subtitle Tools and Settings pages with a clean look,
  native poster rendering and smooth tables. `python subgrab.py` starts the Qt UI when PySide6 is installed
  and falls back to the built-in Tk interface otherwise; release builds bundle PySide6.
- Sources: OpenSubtitles.com (API) and SubSource (API) first; optional fallbacks Podnapisi, Subf2m, YIFY and a
  Subscene community mirror (off by default, clearly labeled as unofficial). Per-source status, retry with the
  next source and a "Test" button for every source.
- Exact file-hash matching (OpenSubtitles hash) plus release-name scoring (group / source / resolution /
  codec / edition). Weak matches are held back for review with preview and manual pick.
- "Why this match" explanations in the manual-pick dialog: every candidate explains in plain words why it
  fits your file (file hash, exact episode, same/different release details).
- Understands real-world file names: S01E02, 1x02, multi-episode (S01E01E02), anime absolute numbering
  ("Show - 03") and editions (Extended, Director's Cut, Remastered). Fuzzy title matching tolerates typos
  and word order.
- Rename video files to clean canonical names ("Title (Year)" / "Title - S01E02") with preview and one-click
  undo; sidecar subtitles are renamed along.
- Automatic subtitle fixes: UTF-8 conversion (Arabic/Persian code pages detected), ASS/VTT to SRT, optional
  ad/watermark removal and hearing-impaired tag removal, optional UTF-8 BOM for older TVs.
- Subtitle tools: shift timing, frame-rate conversion (23.976 <-> 25 ...), re-encode, with .bak safety copy.
- Optional second download language, RAR/7z unpacking through 7-Zip (bundled in release builds).
- Drag and drop, folder watch mode, download queue with cancel and batch downloads.
- Dark mode, Arabic interface with right-to-left layout, posters and details (IMDb public data, needs Pillow).
- Update checker, portable mode, Explorer right-click menu ("Download subtitles with SubGrab").
- API keys and the OpenSubtitles password are stored in the Windows Credential Manager (via the bundled
  `keyring` package); existing plaintext entries are migrated automatically on first run.
- Windows installer (Inno Setup), portable zip, single-file exe, SHA-256 checksums, optional code signing
  in the release workflow.
- Ko-fi support button (repo Sponsor button and README badge).

### Fixed
- Downloads now also retry on "429 Too Many Requests" and honor the server's Retry-After delay (capped at
  30s), on top of retries for server errors and connection drops.
