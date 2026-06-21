"""Applied Fixes card live-refresh watcher (T-016).

Extracted from ``StartupCoordinator`` as a mixin. It is folded into the
coordinator -- a ``QObject`` -- so the ``QFileSystemWatcher`` and debounce
``QTimer`` parent to the live ``MainWindow``. The mixin holds no ``__init__``;
all state (``_main``, ``_log``, ``_last_run_*``) is set by
``StartupCoordinator.__init__`` and accessed via ``self``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


class ManifestWatcherMixin:
    """Watches the session manifest and refreshes the Applied Fixes card."""

    if TYPE_CHECKING:
        # Provided by StartupCoordinator.__init__ (this is a mixin, not a class
        # used on its own). Declared here only so the type checker resolves the
        # cross-class attribute access; no runtime effect.
        _main: Any
        _log: Any
        _last_run_watcher: Any
        _last_run_debounce: Any
        _last_manifest_sig: Any

    def _manifest_sig(self) -> tuple[int, int] | None:
        """Change signature of the session manifest: ``(st_mtime_ns, st_size)``.

        Returns None when the manifest is absent. The manifest's parent is the
        busy CWD root, so ``_on_backups_changed`` compares this signature to
        suppress reloads triggered by unrelated activity (log writes, ``_MEI*``
        and ``./lil_bro/`` temp dirs) -- only a real manifest write or delete
        changes it.
        """
        from src.utils.paths import get_session_backup_path
        try:
            st = get_session_backup_path().stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def _init_last_run_watcher(self) -> None:
        """Watch the CWD root so the Applied Fixes card refreshes on every manifest
        write (a fix) or delete (a revert).

        The manifest now lives at the CWD root (``lil_bro_session_manifest.json``),
        beside the logs. We watch the *directory*, not the file: an atomic
        ``os.replace`` swaps the inode and a file-level watch silently stops after
        the first change on Windows. But the CWD root is busy (logs, ``_MEI*``, the
        ``./lil_bro/`` temp dir), so ``_on_backups_changed`` guards every event
        against a cheap manifest signature (mtime+size) -- unrelated churn costs one
        ``os.stat``, never a reload. Each manifest write fires ``directoryChanged``
        twice (the ``.tmp`` create then the rename), so a 150 ms single-shot timer
        collapses the pair into one reload. Parented to the main window so Qt tears
        it down with it.
        """
        from PySide6.QtCore import QObject

        # Unit tests construct the coordinator with a mock main; the real Qt
        # watcher/timer require a genuine QObject parent. Skip there -- production
        # always passes the MainWindow.
        if not isinstance(self._main, QObject):
            self._log.debug("Applied Fixes watcher skipped: main is not a QObject")
            return
        try:
            from PySide6.QtCore import QFileSystemWatcher, QTimer
            from src.utils.paths import get_session_backup_path

            watch_dir = str(get_session_backup_path().parent)  # CWD root (always exists)
            self._last_manifest_sig = self._manifest_sig()
            self._last_run_debounce = QTimer(self._main)
            self._last_run_debounce.setSingleShot(True)
            self._last_run_debounce.setInterval(150)
            self._last_run_debounce.timeout.connect(self._reload_last_run)

            self._last_run_watcher = QFileSystemWatcher([watch_dir], self._main)
            self._last_run_watcher.directoryChanged.connect(self._on_backups_changed)
        except Exception as exc:
            self._log.warning("Applied Fixes watcher init failed: %s", exc, exc_info=True)

    def _on_backups_changed(self, _path: str) -> None:
        # Some platforms drop the watch after a delete/recreate; re-add defensively.
        try:
            from src.utils.paths import get_session_backup_path
            d = str(get_session_backup_path().parent)
            if self._last_run_watcher is not None and d not in self._last_run_watcher.directories():
                self._last_run_watcher.addPath(d)
        except Exception:
            pass  # best-effort re-add; the signature check below still runs
        # The watched dir is the busy CWD root -- only reload when the manifest
        # itself changed (write or delete), not on unrelated file activity.
        cur = self._manifest_sig()
        if cur == self._last_manifest_sig:
            return
        self._last_manifest_sig = cur
        if self._last_run_debounce is not None:
            self._last_run_debounce.start()

    def _reload_last_run(self) -> None:
        """Re-read the manifest and feed the Applied Fixes card (GUI thread)."""
        try:
            from src.utils.revert import load_manifest
            self._main._revert_view.set_last_run(load_manifest())
        except Exception as exc:
            self._log.warning("Applied Fixes refresh failed: %s", exc, exc_info=True)
