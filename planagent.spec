# -*- mode: python ; coding: utf-8 -*-
import os
import sys

from PyInstaller.utils.hooks import collect_submodules


_CONDA_DLLS = [
    "ffi.dll",
    "LIBBZ2.dll",
    "libcrypto-3-x64.dll",
    "libexpat.dll",
    "liblzma.dll",
    "libssl-3-x64.dll",
    "libzstd.dll",
    "sqlite3.dll",
    "zlib.dll",
]

_CONDA_BIN = None
if sys.platform == "win32":
    candidates = [
        os.environ.get("PLANAGENT_CONDA_BIN", ""),
        r"D:\conda\envs\dl2025\Library\bin",
    ]
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            _CONDA_BIN = candidate
            break

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("openai")
    + collect_submodules("sqlalchemy")
    + collect_submodules("pydantic")
    + collect_submodules("pydantic_settings")
)

a = Analysis(
    ["backend/run_desktop.py"],
    pathex=["backend"],
    binaries=(
        [(os.path.join(_CONDA_BIN, dll), ".") for dll in _CONDA_DLLS]
        if _CONDA_BIN
        else []
    ),
    datas=[("backend/static", "static")],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tests"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Daybreak",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
