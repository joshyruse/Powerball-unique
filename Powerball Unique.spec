# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['scripts/gui_app.py'],
    pathex=['src'],
    binaries=[],
    datas=[('scripts', 'scripts'), ('data', 'data')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Powerball Unique',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Powerball Unique',
)
app = BUNDLE(
    coll,
    name='Powerball Unique.app',
    icon='assets/icon.icns',
    bundle_identifier=None,
)
