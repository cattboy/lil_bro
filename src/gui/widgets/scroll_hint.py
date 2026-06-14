"""Pulsing scroll-down hint floating over a QScrollArea viewport.

A double-ringed "▼▼" chip pinned bottom-center over the viewport of the
scroll area it is parented to. Its amber drop-shadow glow pulses to draw
the eye, and the chip is dismissed for good on the user's first
interaction — a click on it or any scroll — since by then its job
(signalling that more cards lie below) is done.

The pulse starts in ``showEvent`` (visibility-driven), never via timers
scheduled during the splash's nested event loop — the bundled PyInstaller
exe drops those events (see feedback_pyside_nested_loop_qtimer).
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QScrollArea, QToolButton


class ScrollHintArrow(QToolButton):
    """Bottom-center double-ringed "▼▼" chip over *scroll_area*'s viewport."""

    _CHIP = 48        # px — circular chip (border-radius 16 in the QSS)
    _MARGIN = 10      # px gap above the viewport's bottom edge
    _PULSE_MS = 1400  # full glow cycle (8 → 22 → 8 blur); 700ms legs = DESIGN.md "long"
    _SCROLL_MS = 600  # click-scroll animation = DESIGN.md "medium"
    _BLUR_REST = 8.0
    _BLUR_PEAK = 22.0

    def __init__(self, scroll_area: QScrollArea) -> None:
        super().__init__(scroll_area)
        self._area = scroll_area
        self._interacted = False

        self.setObjectName("scrollHintArrow")
        self.setAccessibleName("Scroll for more cards")
        self.setText("▼▼")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(self._CHIP, self._CHIP)

        # The pulse animates the drop-shadow blur: a widget takes a single
        # QGraphicsEffect, so the glow itself pulses (no opacity effect on
        # top, and QSS has no box-shadow to animate). Alpha is kept high so
        # the amber halo's breathe reads clearly against the elevated chip —
        # at low alpha the blur sweep is imperceptible (looks like no pulse).
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setColor(QColor(255, 181, 71, 160))  # amber FFB547 glow
        self._glow.setOffset(0, 0)
        self._glow.setBlurRadius(self._BLUR_REST)
        self.setGraphicsEffect(self._glow)

        self._pulse = QPropertyAnimation(self._glow, b"blurRadius", self)
        self._pulse.setDuration(self._PULSE_MS)
        self._pulse.setStartValue(self._BLUR_REST)
        self._pulse.setKeyValueAt(0.5, self._BLUR_PEAK)
        self._pulse.setEndValue(self._BLUR_REST)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse.setLoopCount(-1)

        self._scroll_anim: QPropertyAnimation | None = None

        vbar = scroll_area.verticalScrollBar()
        vbar.rangeChanged.connect(self._sync)
        vbar.valueChanged.connect(self._on_scrolled)
        self.clicked.connect(self._on_clicked)
        scroll_area.installEventFilter(self)

        self._sync()

    # ── Behavior ─────────────────────────────────────────────────────────

    def _sync(self, *_args) -> None:
        """Show only before the first interaction, while content lies below.

        Once the user scrolls or clicks the chip it is dismissed for good —
        ``_interacted`` latches it hidden so range/value changes never bring
        it back.
        """
        if self._interacted:
            self.setVisible(False)
            return
        vbar = self._area.verticalScrollBar()
        below = vbar.maximum() > 0 and vbar.value() < vbar.maximum()
        self.setVisible(below)
        if below:
            self._reposition()
            self.raise_()

    def _on_scrolled(self, _value: int) -> None:
        # Any scroll (wheel, drag, keys, or the click animation) counts as
        # the first interaction — the attention pulse has done its job.
        self._mark_interacted()
        self._sync()

    def _on_clicked(self) -> None:
        """Smooth-scroll one viewport page down."""
        self._mark_interacted()
        vbar = self._area.verticalScrollBar()
        anim = QPropertyAnimation(vbar, b"value", self)
        anim.setDuration(self._SCROLL_MS)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(vbar.value())
        anim.setEndValue(min(vbar.value() + vbar.pageStep(), vbar.maximum()))
        anim.start()
        self._scroll_anim = anim  # keep alive for the duration

    def _mark_interacted(self) -> None:
        if self._interacted:
            return
        self._interacted = True
        self._stop_pulse()
        self.hide()  # dismissed on first scroll/click — never returns

    def _stop_pulse(self) -> None:
        if self._pulse.state() == QPropertyAnimation.State.Running:
            self._pulse.stop()
        self._glow.setBlurRadius(self._BLUR_REST)

    def _reposition(self) -> None:
        vp = self._area.viewport()
        origin = vp.mapTo(self._area, QPoint(0, 0))
        x = origin.x() + (vp.width() - self.width()) // 2
        y = origin.y() + vp.height() - self.height() - self._MARGIN
        self.move(x, y)

    # ── Qt plumbing ──────────────────────────────────────────────────────

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self._area and event.type() == QEvent.Type.Resize:
            self._sync()
        return super().eventFilter(obj, event)

    def showEvent(self, event) -> None:  # noqa: N802  Qt override
        super().showEvent(event)
        if (
            not self._interacted
            and self._pulse.state() != QPropertyAnimation.State.Running
        ):
            self._pulse.start()

    def hideEvent(self, event) -> None:  # noqa: N802  Qt override
        super().hideEvent(event)
        # Don't burn animation ticks while invisible; showEvent restarts the
        # pulse if the user still hasn't interacted.
        self._stop_pulse()

    def paintEvent(self, event) -> None:  # noqa: N802  Qt override
        # QSS paints the surface, the outer ring (border) and the ▼▼ glyph;
        # we add a second concentric ring just inside it so the chip reads as
        # a double ring. The drop-shadow effect picks this up too, so the
        # inner ring shares the amber glow pulse.
        super().paintEvent(event)
        gap = 4  # px inset from the outer QSS ring (border-radius 16)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(255, 181, 71))  # amber FFB547 — matches outer ring
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inner = self.rect().adjusted(gap, gap, -gap, -gap)
        painter.drawRoundedRect(inner, 16 - gap, 16 - gap)
