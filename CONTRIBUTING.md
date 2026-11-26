# Contributing

Thanks for helping! SubGrab is plain Python 3.9+ with no runtime dependencies (Pillow is optional, for posters).

## Layout
| File | What it is |
|------|------------|
| `subgrab_core.py` | All logic: sources, matching, hashing, subtitle conversion, downloader. **No Tk import** - unit-testable anywhere. |
| `subgrab.py` | The Tk interface (pages, settings, theme, drag & drop). |
| `subgrab_assets.py` | Generated embedded logo - regenerate with `python assets/make_assets.py`. |
| `tests/` | `test_core.py` (logic) and `test_ui_smoke.py` (UI with a stubbed Tk, no display needed). |
| `packaging/` | `build_windows.bat`, Inno Setup script, 7-Zip bundling notes. |

## Develop
```
python -m unittest discover -s tests -v   # must pass before a PR
python subgrab.py                         # run the app
```
Third-party sites change often. When a source breaks, the fastest fix is a small change in `WebSource` (generic
scraper) or the source's class plus a test with a saved HTML/JSON sample in `tests/`. Please attach
`%APPDATA%\SubGrab\debug.log` to bug reports.

## Releasing
1. Bump `VERSION` in `subgrab_core.py` and add a CHANGELOG entry.
2. `git tag v1.2.3 && git push --tags` - the *Release* workflow builds the exe, installer, portable zip and checksums.

## Ground rules
- Keep the core free of GUI imports; keep UI strings wrapped in `T("...")` and add an Arabic translation in `AR`.
- No telemetry, no bundled credentials. Respect each site's terms and rate limits (the code sleeps between requests).
