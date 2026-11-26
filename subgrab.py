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
SubGrab launcher: the Qt Quick (QML) interface when PySide6 is installed
(falling back to the classic Qt widgets UI, then the Tk UI).
All logic lives in subgrab_core.py.

    pip install PySide6   ->  python subgrab.py   (QML UI)
    python subgrab.py     ->  Tk UI (no dependencies)
"""
import os
import sys


def main():
    try:
        from subgrab_qml import main as qml_main
    except ImportError:
        qml_main = None
    if qml_main is not None:
        rc = qml_main() or 0
        if rc != 2 or os.environ.get('SUBGRAB_SELFTEST_OUT'):  # 2 = QML failed to load; fall back to widgets
            sys.exit(rc)
    try:
        from subgrab_qt import main as qt_main
    except ImportError:
        from subgrab_tk import main as tk_main
        tk_main()
        return
    qt_main()


if __name__ == "__main__":
    main()
