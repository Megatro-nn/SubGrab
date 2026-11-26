Optional: put 7z.exe and 7z.dll from your 7-Zip installation in this folder before building.
They are then bundled inside SubGrab.exe so RAR/7z subtitle downloads work without installing 7-Zip.
(build_windows.bat copies them from "C:\Program Files\7-Zip" automatically when 7-Zip is installed.)

7-Zip is LGPL licensed, with an "unRAR restriction" on its RAR code - see https://www.7-zip.org/license.txt
Do not commit 7z.exe / 7z.dll to git (they are in .gitignore); the release workflow copies them at build time.
