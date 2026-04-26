# -*- mode: python ; coding: utf-8 -*-
"""
lil_bro.spec — PyInstaller build specification.

Produces a single portable .exe (onefile mode).
Run via: python -m PyInstaller lil_bro.spec --noconfirm
Or use: python build.py
"""

import os
import sys

block_cipher = None
ROOT = os.path.abspath('.')

# Include lhm-server companion binary if it was built.
# Build step: python build.py  (calls tools/lhm-server/build.ps1 first).
_lhm_server_exe = os.path.join(ROOT, 'tools', 'lhm-server', 'dist', 'lhm-server.exe')
_lhm_license    = os.path.join(ROOT, 'tools', 'lhm-server', 'LICENSE-LHM.txt')
_pawnio_sys     = os.path.join(ROOT, 'tools', 'PawnIO', 'dist', 'PawnIO.sys')

# Include NVIDIA Profile Inspector binary (committed to repo, modified fork with -exportCustomized).
_npi_exe = os.path.join(ROOT, 'tools', 'nvidiaProfileInspector', 'nvidiaProfileInspector.exe')

# pawnio_setup.exe: official NSIS installer for proper Driver Store installation.
# lhm-server embeds it as a resource, but also bundle here as disk fallback.
_pawnio_setup = os.path.join(ROOT, 'tools', 'PawnIO', 'dist', 'pawnio_setup.exe')

_extra_datas = []
if os.path.isfile(_lhm_server_exe):
    _extra_datas.append((_lhm_server_exe, 'tools'))
if os.path.isfile(_lhm_license):
    _extra_datas.append((_lhm_license, 'tools'))
if os.path.isfile(_npi_exe):
    _extra_datas.append((_npi_exe, 'tools'))
# Bundle PawnIO.sys alongside lhm-server.exe as a disk fallback — the .NET
# EmbeddedResource can silently miss it on incremental builds.
if os.path.isfile(_pawnio_sys):
    _extra_datas.append((_pawnio_sys, 'tools'))
if os.path.isfile(_pawnio_setup):
    _extra_datas.append((_pawnio_setup, 'tools'))

a = Analysis(
    [os.path.join(ROOT, 'src', 'main.py')],
    pathex=[ROOT],
    binaries=[],
    datas=_extra_datas,
    hiddenimports=[
        # WMI + pywin32 COM machinery (PyInstaller misses the COM dispatch)
        'wmi',
        'win32com',
        'win32com.client',
        'pythoncom',
        'pywintypes',
        # colorama
        'colorama',
        # psutil
        'psutil',
        # multiprocessing on Windows — Pool needs these explicitly
        'multiprocessing',
        'multiprocessing.pool',
        'multiprocessing.reduction',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Dev/test tools — not needed in the build
        'pytest',
        'unittest',
        'tkinter',
        '_tkinter',
        'PIL',
    ],
    noarchive=False,
)

# Conditionally include llama_cpp if installed at build time
try:
    import llama_cpp
    a.hiddenimports.append('llama_cpp')
except ImportError:
    pass

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='lil_bro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX triggers antivirus false positives
    console=True,       # Terminal app — keep the console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    runtime_tmpdir='.',  # Extract _MEI* to CWD, not %TEMP% — keep all artifacts local
    uac_admin=True,     # Embeds requireAdministrator manifest
    icon=None,          # TODO: Add icon when ready
)
