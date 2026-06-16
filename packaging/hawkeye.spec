# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — standalone hawkeye one-file binary.
# Metadata: v1.3.0 | Scout Contributors | 2026-06-15

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

spec_dir = Path(SPECPATH)
root = spec_dir.parent
pack_dir = root / "scout" / "hawkeye" / "rules" / "pack_v1"
entry = root / "scout" / "hawkeye" / "cli" / "main.py"

datas = [(str(pack_dir), "scout/hawkeye/rules/pack_v1")]

hiddenimports = collect_submodules("scout.hawkeye") + [
    "httpx",
    "yaml",
    "scout.setup.api_url",
    "scout.config",
]

a = Analysis(
    [str(entry)],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["scout_core", "maturin"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="hawkeye",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
