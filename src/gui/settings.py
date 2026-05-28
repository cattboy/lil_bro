"""Thin QSettings wrapper for window geometry + future preferences.

Storage location (Windows): ``HKCU\\Software\\lil_bro\\GUI``. Qt's
QSettings handles the platform mapping for us — same code works on a
Linux dev machine using INI files, even though the production target
is Windows-only.

API surface deliberately small:

- ``Settings.get(key, default)`` / ``Settings.set(key, value)``
- ``Settings.save_geometry(window)`` / ``Settings.restore_geometry(window)``

Future prefs (light mode toggle, default phase selection, debug
toggle, telemetry opt-in) hang off ``get`` / ``set`` with named groups
so we don't proliferate one-off methods.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QWidget


_ORG = "lil_bro"
_APP = "GUI"
_GEOMETRY_KEY = "window/geometry"
_STATE_KEY = "window/state"


class Settings:
    """Wrapper around ``QSettings`` scoped to ``HKCU\\Software\\lil_bro\\GUI``."""

    def __init__(self, organization: str = _ORG, application: str = _APP) -> None:
        self._qs = QSettings(organization, application)

    def get(self, key: str, default: Any = None) -> Any:
        return self._qs.value(key, default)

    def set(self, key: str, value: Any) -> None:
        self._qs.setValue(key, value)

    def sync(self) -> None:
        self._qs.sync()

    # ── Window geometry helpers ────────────────────────────────────────

    def save_geometry(self, window: QWidget) -> None:
        self._qs.setValue(_GEOMETRY_KEY, window.saveGeometry())
        if hasattr(window, "saveState"):
            try:
                self._qs.setValue(_STATE_KEY, window.saveState())
            except Exception:
                pass  # safe: saveState is unsupported on some Qt builds
        self._qs.sync()

    def restore_geometry(self, window: QWidget) -> bool:
        geometry = self._qs.value(_GEOMETRY_KEY)
        if geometry is None:
            return False
        try:
            window.restoreGeometry(geometry)
        except Exception:
            return False
        if hasattr(window, "restoreState"):
            state = self._qs.value(_STATE_KEY)
            if state is not None:
                try:
                    window.restoreState(state)
                except Exception:
                    pass  # safe: restoreState may reject stale state from a prior Qt version
        return True
