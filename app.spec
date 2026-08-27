# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src\\app.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('assets/credit-analysis.png', 'assets'),
        ('assets/credit-analysis.ico', 'assets'),
    ],
    hiddenimports=['reportlab', 'pdfplumber'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Analise de Credito',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/credit-analysis.ico',
)
