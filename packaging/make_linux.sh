#!/usr/bin/env bash
# Usage: make_linux.sh NAME slug icon.png   (run after the PyInstaller build in dist/NAME)
set -euo pipefail
NAME=$1; SLUG=$2; ICON=$3
python3 - "$ICON" "$SLUG.png" <<'PY'
import sys
from PIL import Image
Image.open(sys.argv[1]).convert("RGBA").resize((256, 256)).save(sys.argv[2])
PY
cat > "$SLUG.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$NAME
Comment=Find and download subtitles
Exec=$NAME
Icon=$SLUG
Terminal=false
Categories=AudioVideo;Video;
EOF
chmod +x "dist/$NAME/$NAME"
# tar.gz with launcher entry
rm -rf pkg && mkdir -p "pkg/$NAME"
cp -r "dist/$NAME/." "pkg/$NAME/"
cp "$SLUG.desktop" "$SLUG.png" "pkg/$NAME/"
tar -C pkg -czf "$NAME-linux.tar.gz" "$NAME"
# AppImage
rm -rf AppDir && mkdir -p AppDir/usr/lib
cp -r "dist/$NAME" "AppDir/usr/lib/$NAME"
cp "$SLUG.desktop" "$SLUG.png" AppDir/
cat > AppDir/AppRun <<EOF
#!/bin/sh
HERE="\$(dirname "\$(readlink -f "\$0")")"
exec "\$HERE/usr/lib/$NAME/$NAME" "\$@"
EOF
chmod +x AppDir/AppRun
curl -L -o appimagetool https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool
ARCH=x86_64 ./appimagetool --appimage-extract-and-run AppDir "$NAME-x86_64.AppImage"
chmod +x "$NAME-x86_64.AppImage"
sha256sum "$NAME-linux.tar.gz" "$NAME-x86_64.AppImage" | tee SHA256SUMS-linux.txt
