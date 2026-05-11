from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


class StatusBarWidget(QWidget):
    """Custom 28px bottom status bar: dot + state label, model, session ID."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBarWidget")
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        self._dot = QLabel("●")
        self._dot.setObjectName("sbDot")
        self._dot.setProperty("dotState", "ok")

        self._state_label = QLabel("Idle")
        self._state_label.setObjectName("sbLabel")

        self._sep1 = self._make_sep()
        self._model_label = QLabel("Model: —")
        self._model_label.setObjectName("sbLabel")

        self._sep2 = self._make_sep()
        self._session_label = QLabel("Session: —")
        self._session_label.setObjectName("sbLabel")

        layout.addWidget(self._dot)
        layout.addSpacing(6)
        layout.addWidget(self._state_label)
        layout.addWidget(self._sep1)
        layout.addWidget(self._model_label)
        layout.addWidget(self._sep2)
        layout.addWidget(self._session_label)
        layout.addStretch()

    def _make_sep(self) -> QLabel:
        sep = QLabel("  ·  ")
        sep.setObjectName("sbSep")
        return sep

    def set_state(self, state: str, label: str) -> None:
        """Update the status dot and state label. state is 'idle' or 'run'."""
        dot_state = "run" if state == "run" else "ok"
        self._dot.setProperty("dotState", dot_state)
        self._dot.style().unpolish(self._dot)
        self._dot.style().polish(self._dot)
        self._state_label.setText(label)

    def set_model(self, name: str) -> None:
        self._model_label.setText(f"Model: {name}")

    def set_session(self, sid: str) -> None:
        self._session_label.setText(f"Session: {sid}")
