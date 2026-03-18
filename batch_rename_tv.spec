# PyInstaller spec file for Batch File Renamer
# Run with: pyinstaller batch_rename_tv.spec

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['batch_rename_tv.py'],
    pathex=[SPECPATH],
    binaries=[],
    datas=[],
    hiddenimports=[
        # tkinter submodules that PyInstaller may miss
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        # Optional packages — safely ignored if not installed
        'ttkthemes',
        'tkinterdnd2',
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
    name='BatchRenamer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    # Single-file executable (no dist/ folder needed)
    onefile=True,
    # Hide the console window on Windows (GUI app)
    console=False,
    # Windows-only: set app icon if present
    icon='icon.ico' if sys.platform == 'win32' and Path('icon.ico').exists() else None,
)
