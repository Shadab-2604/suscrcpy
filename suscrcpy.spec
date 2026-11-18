# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for SUSCRCPY 2.0."""

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

added_files = [
    ('resources/icons/suscrcpy.svg', 'resources/icons'),
    ('requirements.txt', '.'),
]

hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'core',
    'core.adb_manager',
    'core.device_manager',
    'core.scrcpy_manager',
    'core.screen_manager',
    'core.app_manager',
    'core.log_manager',
    'core.error_detector',
    'core.log_exporter',
    'core.process_manager',
    'ui',
    'ui.main_window',
    'ui.device_panel',
    'ui.screen_view',
    'ui.ratio_panel',
    'ui.application_panel',
    'ui.logs_panel',
    'ui.styles',
    'platform',
    'platform.base',
    'platform.windows',
    'platform.linux_x11',
    'platform.linux_wayland',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='suscrcpy',
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
    icon='resources/icons/suscrcpy.svg',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='suscrcpy',
)
