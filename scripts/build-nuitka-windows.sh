#!/bin/bash
# Build script for Link4000 Windows executable using Nuitka
#
# This script is for manual/local builds. For CI builds, see .github/workflows/
#
# Requirements:
#   - Windows (native or WSL)
#   - Python 3.11+
#   - Nuitka installed: pip install nuitka
#   - C compiler (MSVC or MinGW64) on PATH
#   - All project dependencies (pyside6, pywin32, etc.)
#
# Usage:
#   bash scripts/build-nuitka-windows.sh
#
# Output:
#   dist/Link4000.exe (standalone executable)

set -euo pipefail

echo "Building Link4000 with Nuitka..."
echo

# Manual Nuitka command (equivalent to what the spec file does):
#
#   nuitka ^
#     --standalone ^
#     --onefile ^
#     --output-filename=Link4000.exe ^
#     --output-dir=dist ^
#     --windows-console-mode=disable ^
#     --windows-icon-from-ico=resources/icon.ico ^
#     --windows-company-name=Link4000 ^
#     --windows-product-name=Link4000 ^
#     --windows-file-version=1.2.1 ^
#     --windows-product-version=1.2.1 ^
#     --enable-plugin=pyside6 ^
#     --include-qt-plugins=platforms,imageformats ^
#     --include-data-dir=resources=resources ^
#     --include-package=link4000 ^
#     --include-module=win32com.shell.shell ^
#     --include-module=win32com.shell.shellcon ^
#     --include-module=win32com.storagecon ^
#     --include-module=pythoncom ^
#     --include-module=pywintypes ^
#     --lto=yes ^
#     --jobs=4 ^
#     --assume-yes-for-downloads ^
#     --remove-output ^
#     --show-progress ^
#     main.py
#
# Or simply:
#   nuitka --config-file=nuitka_project.yml

nuitka \
    --standalone \
    --onefile \
    --output-filename=Link4000.exe \
    --output-dir=dist \
    --windows-console-mode=disable \
    --windows-icon-from-ico=resources/icon.ico \
    --windows-company-name=Link4000 \
    --windows-product-name=Link4000 \
    --windows-file-version=1.2.1 \
    --windows-product-version=1.2.1 \
    --enable-plugin=pyside6 \
    --include-qt-plugins=platforms,imageformats \
    --include-data-dir=resources=resources \
    --include-package=link4000 \
    --include-module=win32com.shell.shell \
    --include-module=win32com.shell.shellcon \
    --include-module=win32com.storagecon \
    --include-module=pythoncom \
    --include-module=pywintypes \
    --lto=yes \
    --jobs=4 \
    --assume-yes-for-downloads \
    --remove-output \
    --show-progress \
    main.py

echo
echo "Build complete: dist/Link4000.exe"
