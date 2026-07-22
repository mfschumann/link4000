# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for Link4000 Windows executable
#
# Build command:
#   pyinstaller link4000.spec
#
# Note: For Windows icon, you can use either:
#   - An .ico file directly (recommended)
#   - A PNG file (PyInstaller will convert it)
#   - Current config uses icon_128dp48.png which PyInstaller converts to .ico
#

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources', 'resources'),
    ],
    hiddenimports=[
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'win32com.shell.shell',
        'win32com.shell.shellcon',
        'win32com.storagecon',
        'pythoncom',
        'pywintypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Link4000',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Link4000 is a hybrid CLI/GUI application. console=True is required so
    # commands like ``link4000.exe --show-config`` can write to stdout. The
    # side effect is that a console window is also shown when the EXE is
    # launched from Explorer; if a GUI-only launcher is desired, build a
    # second EXE target with console=False.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='resources/icon.ico',
)
