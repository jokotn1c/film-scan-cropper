#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt -r requirements-build.txt
python3 -m PyInstaller --noconfirm --clean --distpath dist-macos-arm64 --workpath build-macos-arm64 FilmCrop-RAW-mac-arm64.spec
ditto -c -k --sequesterRsrc --keepParent dist-macos-arm64/FilmCrop-RAW.app dist-macos-arm64/FilmCrop-RAW-mac-arm64.zip
shasum -a 256 dist-macos-arm64/FilmCrop-RAW-mac-arm64.zip > dist-macos-arm64/FilmCrop-RAW-mac-arm64.sha256
