"""AI Setup model download dialog (HuggingFace GGUF, ~4 GB).

Renders MB downloaded / total, transfer rate, ETA, cancel button. The
actual download work is performed by a separate QThread worker that
streams ``set_progress(downloaded_bytes, total_bytes)`` calls into
this dialog; the dialog itself doesn't touch the network.

Behavior contract:
- Cancel → ``cancel_requested`` flips True, dialog rejects.
- ``set_done()`` accepts the dialog with a triumph message.
- ``set_error(msg)`` swaps into an error state with Retry/Cancel.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class AISetupDialog(QDialog):
    """Branded download progress dialog for the GGUF model."""

    cancel_clicked = Signal()
    retry_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Setup")
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setAccessibleName("AI Setup dialog")

        self._cancel_requested = False
        self._started_at = time.monotonic()
        self._last_bytes = 0
        self._last_t = self._started_at

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(12)

        title = QLabel("Downloading AI model")
        title.setObjectName("sectionHeader")
        layout.addWidget(title)

        self._status = QLabel("Connecting to HuggingFace…")
        self._status.setObjectName("cardLabel")
        layout.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        layout.addWidget(self._bar)

        meta = QHBoxLayout()
        self._size_label = QLabel("0 MB / ?")
        self._size_label.setObjectName("cardLabel")
        meta.addWidget(self._size_label)
        meta.addStretch(1)
        self._rate_label = QLabel("")
        self._rate_label.setObjectName("cardLabel")
        meta.addWidget(self._rate_label)
        layout.addLayout(meta)

        self._eta_label = QLabel("")
        self._eta_label.setObjectName("cardLabel")
        layout.addWidget(self._eta_label)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setVisible(False)
        self.retry_btn.clicked.connect(self._on_retry)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        actions.addWidget(self.retry_btn)
        actions.addWidget(self.cancel_btn)
        layout.addLayout(actions)

    # ── Slots called by the download worker ───────────────────────────

    def set_progress(self, downloaded_bytes: int, total_bytes: int | None) -> None:
        if total_bytes and total_bytes > 0:
            pct = int(downloaded_bytes * 100 / total_bytes)
            self._bar.setValue(min(100, max(0, pct)))
            self._size_label.setText(
                f"{_mb(downloaded_bytes)} MB / {_mb(total_bytes)} MB"
            )
        else:
            self._size_label.setText(f"{_mb(downloaded_bytes)} MB")

        now = time.monotonic()
        dt = max(0.001, now - self._last_t)
        rate = (downloaded_bytes - self._last_bytes) / dt
        if rate > 0:
            self._rate_label.setText(f"{_mb(int(rate))} MB/s")
            if total_bytes and total_bytes > downloaded_bytes:
                remaining = (total_bytes - downloaded_bytes) / rate
                self._eta_label.setText(f"ETA: {_format_eta(remaining)}")
        self._last_t = now
        self._last_bytes = downloaded_bytes
        self._status.setText("Downloading…")

    def set_done(self, message: str = "AI features enabled. Now we're cooking.") -> None:
        self._status.setText(message)
        self._bar.setValue(100)
        self._eta_label.setText("")
        self._rate_label.setText("")
        self.cancel_btn.setText("Close")
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self.accept)

    def set_error(self, message: str) -> None:
        self._status.setText(f"Download failed: {message}")
        self._eta_label.setText("")
        self._rate_label.setText("")
        self.retry_btn.setVisible(True)

    # ── Result accessors ──────────────────────────────────────────────

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested

    # ── Internals ─────────────────────────────────────────────────────

    def _on_cancel(self) -> None:
        self._cancel_requested = True
        self.cancel_clicked.emit()
        self.reject()

    def _on_retry(self) -> None:
        self.retry_btn.setVisible(False)
        self._status.setText("Reconnecting…")
        self._bar.setValue(0)
        self._cancel_requested = False
        self._started_at = time.monotonic()
        self._last_t = self._started_at
        self._last_bytes = 0
        self.retry_clicked.emit()


def _mb(byte_count: int) -> int:
    return int(byte_count / (1024 * 1024))


def _format_eta(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m:02d}m"
