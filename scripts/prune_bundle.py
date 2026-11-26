#!/usr/bin/env python3
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
"""Trim unused Qt modules from a PyInstaller onedir build.

PyInstaller's --collect-all pulls every Qt shared library and QML module
into the bundle, including WebEngine (~200 MB), Quick3D and others that
SubGrab never imports. This removes them after the build. Safe to re-run.
Usage: python scripts/prune_bundle.py dist/SubGrab
"""
import os
import shutil
import sys

# Qt modules the app never loads, without the version digit: the Windows/Linux
# name (Qt6WebEngineCore.dll / libQt6WebEngineCore.so.6) and the macOS
# framework binary (QtWebEngineCore.framework/.../QtWebEngineCore) both
# start with these prefixes.
_BASE = [
    "WebEngineCore", "WebEngineQuick", "WebEngineWidgets", "WebChannel",
    "WebView", "Pdf", "Quick3D", "Charts", "DataVisualization", "Multimedia",
    "3D", "TextToSpeech", "Bluetooth", "Nfc", "Positioning", "Location",
    "Sensors", "SerialPort", "SerialBus", "RemoteObjects", "Scxml",
    "VirtualKeyboard", "Designer", "Help", "Test", "Sql", "Graphs",
    "ShaderTools", "SpatialAudio", "WebSockets", "HttpServer",
    "QuickDialogs2", "Labs",
]
LIB_PREFIXES = [p + b for p in ("Qt6", "Qt", "libQt6", "libQt") for b in _BASE]

# QML import directories the app never imports (Main.qml uses only
# QtQuick, QtQuick.Controls and QtQuick.Layouts).
QML_DIRS = [
    "QtWebEngine", "QtQuick3D", "Qt3D", "QtCharts", "QtDataVisualization",
    "QtGraphs", "QtMultimedia", "QtLocation", "QtPositioning", "QtSensors",
    "Qt5Compat", "QtTest", "QtWebChannel", "QtWebView", "QtPdf",
    "QtVirtualKeyboard", "QtScxml", "QtRemoteObjects", "QtTextToSpeech",
    os.path.join("Qt", "labs"),
]


def main(root):
    removed = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        for d in list(dirnames):
            if d.endswith(".framework") and d[:-10].startswith(tuple(p + b for p in ("Qt6", "Qt") for b in _BASE)):
                shutil.rmtree(os.path.join(dirpath, d))
                dirnames.remove(d)
                removed += 1
        for f in filenames:
            if f.startswith(tuple(LIB_PREFIXES)):
                os.remove(os.path.join(dirpath, f))
                removed += 1
    qml_root = None
    for dirpath, dirnames, _ in os.walk(root):
        if os.path.basename(dirpath) == "qml" and os.path.basename(os.path.dirname(dirpath)) == "Qt":
            qml_root = dirpath
            break
    if qml_root:
        for d in QML_DIRS:
            target = os.path.join(qml_root, d)
            if os.path.isdir(target):
                shutil.rmtree(target)
                removed += 1
        translations = os.path.join(os.path.dirname(qml_root), "translations")
        if os.path.isdir(translations):
            shutil.rmtree(translations)
            removed += 1
    print(f"pruned {removed} unused Qt files/dirs from {root}")


if __name__ == "__main__":
    main(sys.argv[1])
