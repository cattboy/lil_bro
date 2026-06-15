"""Dashboard card for the DLSS preset one-click fix.

Shown on the Dashboard when nvidia-smi detects a supported NVIDIA consumer GPU
(RTX 20/30/40/50 series) and NPI is available. The Apply button emits
``apply_requested("nvidia_dlss_preset")``. The Quality/FPS switch emits
``priority_changed("quality"|"fps")`` when flipped; the switch makes no system
change on its own — only Apply does.

Reuses MonitorRefreshCard's QSS objectNames (``monitorCard``, ``pollLabel``,
``pollStatus``, ``primary``) so no new theme rules are required. The Quality/FPS
control is a custom-painted :class:`ToggleSwitch` (a real animated pill switch),
flanked by two clickable labels whose colour reflects the active side — replacing
the old segmented two-button toggle whose fixed height cropped the label text.
"""

from __future__ import annotations

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.gui.theme import repolish, set_apply_busy
from src.gui.theme.tokens import COLORS, FONTS

_CHECK_NAME = "nvidia_dlss_preset"


def _blend(c0: QColor, c1: QColor, t: float) -> QColor:
    """Linear RGB interpolation between two colours (t clamped to 0..1)."""
    t = max(0.0, min(1.0, t))
    return QColor(
        round(c0.red() + (c1.red() - c0.red()) * t),
        round(c0.green() + (c1.green() - c0.green()) * t),
        round(c0.blue() + (c1.blue() - c0.blue()) * t),
    )


def _label_qss(active: bool) -> str:
    """Inline QSS for a flanking toggle label — accent when its side is active."""
    color = COLORS["accent"] if active else COLORS["text_muted"]
    weight = 600 if active else 500
    return (
        f'font-family: "{FONTS["sans"]}"; font-size: 12px; '
        f"color: {color}; font-weight: {weight};"
    )


class ToggleSwitch(QAbstractButton):
    """An animated on/off pill switch — the knob slides left↔right.

    A checkable ``QAbstractButton``: unchecked = left position, checked = right.
    The knob slide is a 150ms ``QPropertyAnimation`` on the private ``offset``
    property (0.0 left → 1.0 right), and the track colour blends grey→accent over
    the same travel. ``toggled`` fires for both programmatic and user changes (it
    drives the animation); ``clicked`` fires only on real user interaction, so the
    card can distinguish a user flip from a programmatic ``setChecked``.
    """

    _TRACK_W = 44
    _TRACK_H = 24
    _MARGIN = 3  # gap between knob and track edge

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Keep the WASD/Enter input layer off the switch — Apply is the only
        # keyboard target in this card.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(150)  # DESIGN.md motion: "short"
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.toggled.connect(self._animate_to_state)

        self._track_off = QColor(COLORS["border_default"])
        self._track_on = QColor(COLORS["accent"])
        self._knob = QColor(COLORS["text_primary"])

    def sizeHint(self) -> QSize:  # noqa: N802  Qt override
        return QSize(self._TRACK_W, self._TRACK_H)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate_to_state(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._offset)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, _event) -> None:  # noqa: N802  Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        # Centre a fixed-size pill so any layout stretch can't distort it.
        track_y = (self.height() - self._TRACK_H) / 2
        track = QRectF(0, track_y, self._TRACK_W, self._TRACK_H)
        radius = self._TRACK_H / 2
        painter.setBrush(_blend(self._track_off, self._track_on, self._offset))
        painter.drawRoundedRect(track, radius, radius)

        # Knob travels between the two inset end positions.
        knob_d = self._TRACK_H - 2 * self._MARGIN
        travel = self._TRACK_W - knob_d - 2 * self._MARGIN
        knob_x = self._MARGIN + travel * self._offset
        painter.setBrush(self._knob)
        painter.drawEllipse(QRectF(knob_x, track_y + self._MARGIN, knob_d, knob_d))


class _ClickableLabel(QLabel):
    """A QLabel that emits ``clicked`` on a left-button press."""

    clicked = Signal()

    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802  Qt override
        # Honour the disabled state: a plain QLabel does not suppress its own
        # mouse handling when disabled, so without this guard a click would
        # still fire ``clicked`` mid-apply (when set_applying has disabled it).
        if not self.isEnabled():
            super().mousePressEvent(event)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class NvidiaDlssCard(QFrame):
    """DLSS preset card. Emits ``apply_requested("nvidia_dlss_preset")`` and
    ``priority_changed("quality"|"fps")``."""

    apply_requested = Signal(str)
    priority_changed = Signal(str)

    def __init__(self, title: str, button_label: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("monitorCard")
        self.setAccessibleName(f"{title} card")

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(4)

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("pollLabel")
        left.addWidget(self._title_lbl)

        self._status_lbl = QLabel("—")
        self._status_lbl.setObjectName("pollStatus")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setProperty("sev", "medium")
        left.addWidget(self._status_lbl)

        # Quality ⟷ FPS switch. The switch is unchecked = Quality, checked = FPS.
        # Both flanking labels are clickable; the active side is accent-coloured.
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(8)
        self._quality_lbl = _ClickableLabel("Quality")
        self._toggle = ToggleSwitch()
        self._fps_lbl = _ClickableLabel("FPS")
        toggle_row.addWidget(self._quality_lbl)
        toggle_row.addWidget(self._toggle)
        toggle_row.addWidget(self._fps_lbl)
        toggle_row.addStretch()
        left.addLayout(toggle_row)

        self._toggle.clicked.connect(self._on_toggle_clicked)
        self._toggle.toggled.connect(lambda _checked: self._refresh_labels())
        self._quality_lbl.clicked.connect(lambda: self._select_via_label("quality"))
        self._fps_lbl.clicked.connect(lambda: self._select_via_label("fps"))
        self._refresh_labels()

        root.addLayout(left, 1)

        self._apply_btn = QPushButton(button_label)
        self._apply_btn.setObjectName("primary")
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.setFixedWidth(140)
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        root.addWidget(self._apply_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_gpu(self, gpu_name: str, status_text: str, tooltip: str = "") -> None:
        """Populate the card with the detected GPU and the recommended action."""
        self._status_lbl.setText(f"{gpu_name} — {status_text}" if gpu_name else status_text)
        self._status_lbl.setToolTip(tooltip)
        repolish(self._status_lbl)

    def set_priority(self, priority: str) -> None:
        """Reflect the current priority on the switch (no signal emitted)."""
        self._toggle.setChecked(priority == "fps")
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        quality_active = not self._toggle.isChecked()
        self._quality_lbl.setStyleSheet(_label_qss(quality_active))
        self._fps_lbl.setStyleSheet(_label_qss(not quality_active))

    def _on_toggle_clicked(self, checked: bool) -> None:
        self.priority_changed.emit("fps" if checked else "quality")

    def _select_via_label(self, priority: str) -> None:
        target = priority == "fps"
        if self._toggle.isChecked() == target:
            return  # clicking the already-active label is a no-op
        self._toggle.setChecked(target)  # fires toggled → labels refresh
        self.priority_changed.emit(priority)

    def _on_apply_clicked(self) -> None:
        self.apply_requested.emit(_CHECK_NAME)

    def set_applying(self, applying: bool) -> None:
        """Reflect an in-flight fix: lock the Apply button AND the Quality/FPS
        control. The toggle makes no system change on its own, but locking it
        avoids a confusing mid-apply flip (and a stale priority write)."""
        set_apply_busy(self._apply_btn, applying)
        self._toggle.setEnabled(not applying)
        self._quality_lbl.setEnabled(not applying)
        self._fps_lbl.setEnabled(not applying)
