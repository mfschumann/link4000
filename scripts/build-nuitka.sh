#!/bin/bash
# Build script for Link4000 using Nuitka
#
# This script is for manual/local builds. For CI builds, see .github/workflows/
#
# Requirements:
#   - Python 3.11+
#   - Nuitka installed: pip install nuitka
#   - C compiler (gcc/clang on Linux, MSVC/MinGW64 on Windows)
#   - All project dependencies (pyside6, etc.)
#
# Usage:
#   bash scripts/build-nuitka.sh
#
# Auto-detects the platform (Linux/Windows) and applies the right flags.
#
# Output:
#   dist/Link4000 (Linux) or dist/Link4000.exe (Windows)

set -euo pipefail

# Detect platform
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
  PLATFORM="windows"
  OUTPUT_NAME="Link4000.exe"
  PLATFORM_FLAGS=(
    --windows-console-mode=disable
    --windows-icon-from-ico=resources/icon.ico
    --windows-company-name=Link4000
    --windows-product-name=Link4000
    --windows-file-version=1.2.1
    --windows-product-version=1.2.1
    --include-data-dir=.pixi/envs/dev/Library/qt6/plugins=qt6_plugins
    --include-module=win32com.shell.shell
    --include-module=win32com.shell.shellcon
    --include-module=win32com.storagecon
    --include-module=pythoncom
    --include-module=pywintypes
  )
else
  PLATFORM="linux"
  OUTPUT_NAME="Link4000"
  PLATFORM_FLAGS=(
    --include-data-dir=.pixi/envs/dev/lib/qt6/plugins=qt6_plugins
  )
fi

echo "Building Link4000 with Nuitka ($PLATFORM)..."
echo

# Manual Nuitka command (equivalent to what this script does):
#
# Note: We do NOT use --enable-plugin=pyside6 because Nuitka's PySide6
# plugin generates a post-load hook (PySide6-postLoad.py) that patches
# QObject.connect() and is incompatible with Python 3.13 + recent PySide6.
# Instead, we manually include PySide6 and Qt plugins.
#
# Qt plugins (platform, imageformats) are included via --include-data-dir
# pointing to the Qt plugins directory in the pixi environment.
#
# Linux:
#   nuitka \
#     --standalone \
#     --onefile \
#     --output-filename=Link4000 \
#     --output-dir=dist \
#     --include-package=PySide6 \
#     --include-data-dir=.pixi/envs/dev/lib/qt6/plugins=qt6_plugins \
#     --include-data-dir=resources=resources \
#     --include-package=link4000 \
#     --nofollow-import-to=_pyrepl \
#     --lto=yes \
#     --jobs=4 \
#     --assume-yes-for-downloads \
#     --remove-output \
#     --show-progress \
#     main.py
#
# Windows:
#   nuitka ^
#     --standalone ^
#     --onefile ^
#     --output-filename=Link4000.exe ^
#     --output-dir=dist ^
#     --windows-console-mode=disable ^
#     --windows-icon-from-ico=resources/icon.ico ^
#     --include-package=PySide6 ^
#     --include-data-dir=.pixi/envs/dev/Library/qt6/plugins=qt6_plugins ^
#     --include-data-dir=resources=resources ^
#     --include-package=link4000 ^
#     --include-module=win32com.shell.shell ^
#     --include-module=win32com.shell.shellcon ^
#     --include-module=win32com.storagecon ^
#     --include-module=pythoncom ^
#     --include-module=pywintypes ^
#     --nofollow-import-to=_pyrepl ^
#     --lto=yes ^
#     --jobs=4 ^
#     --assume-yes-for-downloads ^
#     --remove-output ^
#     --show-progress ^
#     main.py

pixi run -e dev nuitka \
    --standalone \
    --onefile \
    --output-filename="$OUTPUT_NAME" \
    --output-dir=dist \
    --include-package=PySide6 \
    --include-data-dir=resources=resources \
    --include-package=link4000 \
    --nofollow-import-to=_pyrepl \
    "${PLATFORM_FLAGS[@]}" \
    --lto=yes \
    --jobs=4 \
    --assume-yes-for-downloads \
    --remove-output \
    --show-progress \
    main.py

echo
echo "Build complete: dist/$OUTPUT_NAME"
