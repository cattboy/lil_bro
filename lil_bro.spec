# -*- mode: python ; coding: utf-8 -*-
"""
lil_bro.spec — PyInstaller build specification.

Produces a single windowed onefile .exe. Default launch (double-click,
shortcut, ``lil_bro.exe`` no args) opens the PySide6 GUI.
``lil_bro.exe --terminal`` triggers ``console_attach.attach()`` so the
legacy CLI runs in the parent console (or a fresh AllocConsole window).

Run via: python -m PyInstaller lil_bro.spec --noconfirm
Or use:   python build.py
"""

import os

block_cipher = None
ROOT = os.path.abspath('.')

# ── Companion binaries -------------------------------------------------
_lhm_server_exe = os.path.join(ROOT, 'tools', 'lhm-server', 'dist', 'lhm-server.exe')
_lhm_license    = os.path.join(ROOT, 'tools', 'lhm-server', 'LICENSE-LHM.txt')
_npi_exe        = os.path.join(ROOT, 'tools', 'nvidiaProfileInspector', 'nvidiaProfileInspector.exe')
_pawnio_setup   = os.path.join(ROOT, 'tools', 'PawnIO', 'dist', 'pawnio_setup.exe')

_extra_datas = []
if os.path.isfile(_lhm_server_exe):
    _extra_datas.append((_lhm_server_exe, 'tools'))
if os.path.isfile(_lhm_license):
    _extra_datas.append((_lhm_license, 'tools'))
if os.path.isfile(_npi_exe):
    _extra_datas.append((_npi_exe, 'tools'))
if os.path.isfile(_pawnio_setup):
    _extra_datas.append((_pawnio_setup, 'tools'))

# ── GUI resources (bundled .ttf fonts) --------------------------------
_resources_dir = os.path.join(ROOT, 'resources')
_fonts_dir     = os.path.join(_resources_dir, 'fonts')

if os.path.isdir(_fonts_dir):
    for _name in os.listdir(_fonts_dir):
        if _name.lower().endswith('.ttf'):
            _extra_datas.append((os.path.join(_fonts_dir, _name), 'resources/fonts'))


a = Analysis(
    [os.path.join(ROOT, 'src', 'main.py')],
    pathex=[ROOT],
    binaries=[],
    datas=_extra_datas,
    hiddenimports=[
        # WMI + pywin32 COM machinery
        'wmi',
        'win32com',
        'win32com.client',
        'pythoncom',
        'pywintypes',
        # colorama
        'colorama',
        # psutil
        'psutil',
        # multiprocessing on Windows
        'multiprocessing',
        'multiprocessing.pool',
        'multiprocessing.reduction',
        # PySide6 GUI surface — explicit hints so PyInstaller's static
        # analysis doesn't miss the lazily-imported widgets.
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'src.console_attach',
        'src.gui.app',
        'src.gui.bridge',
        'src.gui.cap_notifier',
        'src.gui.pipeline_controller',
        'src.gui.settings',
        'src.gui.signals',
        'src.gui.startup',
        'src.gui.startup_coordinator',
        'src.gui.theme',
        'src.gui.worker',
        'src.gui.input.wasd_filter',
        'src.gui.widgets.ai_setup_dialog',
        'src.gui.widgets.batch_selection_dialog',
        'src.gui.widgets.confirm_dialog',
        'src.gui.widgets.dashboard',
        'src.gui.widgets.dialogs',
        'src.gui.widgets.last_run_card',
        'src.gui.widgets.monitor_refresh_card',
        'src.gui.widgets.mouse_poll_card',
        'src.gui.widgets.mouse_ready_dialog',
        'src.gui.widgets.nvidia_profile_card',
        'src.gui.widgets.output_panel',
        'src.gui.widgets.output_view',
        'src.gui.widgets.benchmark_row',
        'src.gui.widgets.revert_view',
        'src.gui.widgets.splash',
        'src.gui.widgets.stat_card',
        'src.gui.widgets.status_bar_widget',
        'src.gui.widgets.thermal_chart',
        'src.gui.windows.main_window',
        'src.agent_tools.mouse',
        'src.agent_tools.quick_status',
        # src.utils helpers re-exported via formatting
        'src.utils._console',
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
        # Strip Qt subsystems lil_bro doesn't use to keep the bundle
        # under the 200 MB target. Each line saves ~5-30 MB.
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtQuick',
        'PySide6.QtQuick3D',
        'PySide6.QtQml',
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebChannel',
        'PySide6.QtWebSockets',
        'PySide6.Qt3DCore',
        'PySide6.Qt3DRender',
        'PySide6.Qt3DInput',
        'PySide6.Qt3DLogic',
        'PySide6.Qt3DAnimation',
        'PySide6.Qt3DExtras',
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtPositioning',
        'PySide6.QtLocation',
        'PySide6.QtSerialPort',
        'PySide6.QtSensors',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
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
    pyz, a.scripts, a.binaries, a.datas, [],
    name='lil_bro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX triggers antivirus false positives
    console=False,       # GUI-default; --terminal flag pops a console at runtime
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    runtime_tmpdir='.',  # Extract _MEI* to CWD, not %TEMP%
    uac_admin=True,      # Embeds requireAdministrator manifest
    icon=None,           # TODO: Add icon when ready
)
