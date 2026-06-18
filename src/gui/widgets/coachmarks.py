"""First-run coachmarks: in-context arrow-bubble callouts over the live Dashboard.

A non-blocking onboarding tour for the FAQ-Instructions design
(``cattboy-FAQ-Instructions-design-20260617-134435.md``). Arrow-bubble callouts
float over the *real* MainWindow chrome and point at the actual controls a
first-timer will press — ``Start Optimization`` (the guided pipeline), a live
quick-fix card, and ``Revert Changes`` (the safety net). Each target gets a
gentle pulsing accent ring (no screen dim). The same copy is wired as an
always-on hover tooltip on those controls, so the teaching persists past run one.

Shown once on first launch (gated on ``Settings.has_seen_coachmarks``); replayable
any time from the sidebar ``Help / FAQ (H)`` button.

Navigation reuses the app's existing ``WASDInputFilter`` (``src/gui/input/wasd_filter.py``):
the active bubble's ``Next (W)`` button is made the sole *default* button while it
shows, so a ``W`` press clicks it with no changes to the filter — the user's first
rep of the app-wide W=proceed convention. ``Esc`` / ``S`` (Skip) / clicking outside
the bubble dismisses (handled by an event filter installed only while the tour is
active). ``S`` mirrors the bubble's ``Skip (S)`` button and the app-wide W=proceed /
S=back convention — the controller's event filter consumes it so it never reaches the
main window's (no-op-while-idle) stop path.

Bundled-exe note: the controller is created in ``MainWindow.__init__`` (pre-allocated
like the dashboard cards), and the first-run show is scheduled from
``MainWindow.showEvent`` on the first show. ``show()`` is called from ``app.run()``
*after* ``splash.exec()`` returns, so showEvent runs in the ``app.exec()`` lead-in,
never the splash's nested loop — the ``QTimer`` is not dropped in the PyInstaller
build (see ``feedback_pyside_nested_loop_qtimer`` / ``scroll_hint.py``). A short
readiness poll waits for the dashboard's quick-fix cards to wire before anchoring.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.theme import COLORS, FONTS

# ── Bubble geometry constants ───────────────────────────────────────────────
BUBBLE_W = 332      # total widget width (incl. glow + arrow margins)
GLOW = 16           # outer margin reserved so the drop-shadow glow has room
PAD = 16            # inner text padding inside the body rect
ARROW = 12          # arrow depth (also the body inset on the arrow edge)
ARROW_HALF = 9      # arrow base half-width
RADIUS = 10         # body corner radius
GAP = 8             # gap between the target and the arrow tip

_OPPOSITE = {"right": "left", "left": "right", "top": "bottom", "bottom": "top"}

# Delay before the first-run tour appears, so the dashboard's first layout/paint
# pass has settled and target rects are valid (DESIGN.md "medium" ≈ 200ms).
_SETTLE_MS = 220
_RETRY_MS = 200               # poll interval while waiting for dashboard wiring
_MAX_FIRST_RUN_ATTEMPTS = 30  # ~6s ceiling so the first-run tour never stalls


# ── Coachmark copy (single source — reused for bubbles AND hover tooltips) ───
# Brand voice per DESIGN.md: "the friend who knows computers" — the playful YOLO
# energy carries the safety reassurance in the same breath (trust + fun arrive
# together for an admin-elevated tool).
BEATS: list[dict[str, str]] = [
    {
        "name": "optimize",
        "side": "right",
        "title": "Start Optimization",
        "body": (
            "lil_bro scans your rig, holding your hand through each fix. "
            "Nothing touches your PC without approval."
        ),
    },
    {
        "name": "fix",
        "side": "left",
        "title": "Card quick fixes",
        "body": (
            "Or knock out fixes one at a time in the DASHBOARD."
        ),
    },
    {
        "name": "revert",
        "side": "right",
        "title": "Revert Changes",
        "body": (
            "Changed your mind? Revert rolls back everything lil_bro did this "
            "session — always quick save!"
        ),
    },
]

_BEAT_BY_NAME = {b["name"]: b for b in BEATS}


def tooltip_html(title: str, body: str) -> str:
    """The same copy a beat shows, formatted for an always-on hover tooltip."""
    return (
        f"<div style='max-width:280px'>"
        f"<b style='color:{COLORS['accent']}'>{title}</b><br>{body}</div>"
    )


def _is_descendant(widget: QObject | None, ancestor: QWidget) -> bool:
    """True if *widget* is *ancestor* or any of its descendants."""
    node = widget
    while node is not None:
        if node is ancestor:
            return True
        node = node.parent()
    return False


# ── Arrow-bubble callout ────────────────────────────────────────────────────


class CoachmarkBubble(QWidget):
    """Frameless, brand-styled callout: a title + wrapped body + Skip/Next buttons,
    with a directional arrow drawn toward its target.

    Painted entirely in ``paintEvent`` (rounded body united with the arrow
    triangle) over a translucent background, with an accent drop-shadow glow. The
    arrow edge is the side *opposite* to where the bubble sits relative to its
    target. ``next_btn`` is exposed so the controller can make it the sole default
    button (W=proceed via the global WASDInputFilter).
    """

    def __init__(self, title: str, body: str, side: str,
                 on_next, on_skip, last: bool, parent: QWidget) -> None:
        super().__init__(parent)
        self.side = side
        self.arrow_edge = _OPPOSITE[side]
        self._arrow_pos: float | None = None  # along-edge coord (body-local)

        self.setObjectName("coachmarkBubble")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Never steal the active-window status (keeps the WASDInputFilter's
        # surface = MainWindow, so its W still finds our default button).
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedWidth(BUBBLE_W)

        e = self.arrow_edge
        lay = QVBoxLayout(self)
        lay.setContentsMargins(
            GLOW + PAD + (ARROW if e == "left" else 0),
            GLOW + PAD + (ARROW if e == "top" else 0),
            GLOW + PAD + (ARROW if e == "right" else 0),
            GLOW + PAD + (ARROW if e == "bottom" else 0),
        )
        lay.setSpacing(10)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("coachmarkTitle")
        title_lbl.setStyleSheet(
            f"color:{COLORS['accent']}; font-family:'{FONTS['mono']}'; font-size:13px;"
            f"font-weight:700; letter-spacing:0.04em;"
        )
        lay.addWidget(title_lbl)

        body_lbl = QLabel(body)
        body_lbl.setObjectName("coachmarkBody")
        body_lbl.setWordWrap(True)
        body_lbl.setTextFormat(Qt.TextFormat.RichText)
        body_lbl.setStyleSheet(
            f"color:{COLORS['text_primary']}; font-family:'{FONTS['sans']}'; font-size:13px;"
        )
        lay.addWidget(body_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)

        # Skip (S): the bubble's secondary dismiss. S is wired in the controller's
        # eventFilter (mirrors Next/W), so the label advertises that key like
        # next_btn advertises (W).
        self.skip_btn = QPushButton("Skip (S)")
        self.skip_btn.setObjectName("secondary")
        # Secondary must not auto-default, or the WASD filter's W could click it.
        self.skip_btn.setAutoDefault(False)
        self.skip_btn.setDefault(False)
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.clicked.connect(on_skip)
        btn_row.addWidget(self.skip_btn)

        self.next_btn = QPushButton("Done (W)" if last else "Next (W)")
        self.next_btn.setObjectName("primary")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(on_next)
        btn_row.addWidget(self.next_btn)
        lay.addLayout(btn_row)

        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(30)
        glow.setColor(QColor(0, 229, 204, 150))
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)

        self.adjustSize()

    def set_arrow_pos(self, along: float) -> None:
        self._arrow_pos = along
        self.update()

    def _body_rect(self) -> QRectF:
        e = self.arrow_edge
        x0 = GLOW + (ARROW if e == "left" else 0)
        y0 = GLOW + (ARROW if e == "top" else 0)
        x1 = self.width() - GLOW - (ARROW if e == "right" else 0)
        y1 = self.height() - GLOW - (ARROW if e == "bottom" else 0)
        return QRectF(x0, y0, x1 - x0, y1 - y0)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt override)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        body = self._body_rect()
        path = QPainterPath()
        path.addRoundedRect(body, RADIUS, RADIUS)

        e = self.arrow_edge
        if e in ("left", "right"):
            lo, hi = body.top() + RADIUS + ARROW_HALF, body.bottom() - RADIUS - ARROW_HALF
            ac = body.center().y() if self._arrow_pos is None else self._arrow_pos
            ac = max(lo, min(hi, ac))
            if e == "left":
                tip, b1, b2 = (body.left() - ARROW, ac), (body.left(), ac - ARROW_HALF), (body.left(), ac + ARROW_HALF)
            else:
                tip, b1, b2 = (body.right() + ARROW, ac), (body.right(), ac - ARROW_HALF), (body.right(), ac + ARROW_HALF)
        else:
            lo, hi = body.left() + RADIUS + ARROW_HALF, body.right() - RADIUS - ARROW_HALF
            ac = body.center().x() if self._arrow_pos is None else self._arrow_pos
            ac = max(lo, min(hi, ac))
            if e == "top":
                tip, b1, b2 = (ac, body.top() - ARROW), (ac - ARROW_HALF, body.top()), (ac + ARROW_HALF, body.top())
            else:
                tip, b1, b2 = (ac, body.bottom() + ARROW), (ac - ARROW_HALF, body.bottom()), (ac + ARROW_HALF, body.bottom())

        tri = QPainterPath()
        tri.addPolygon(QPolygonF([QPoint(*map(round, tip)),
                                  QPoint(*map(round, b1)),
                                  QPoint(*map(round, b2))]))
        full = path.united(tri)

        p.fillPath(full, QBrush(QColor(COLORS["elevated"])))
        pen = QPen(QColor(COLORS["accent"]))
        pen.setWidth(2)
        p.strokePath(full, pen)


# ── Highlight overlay (pulsing accent rings around the teaching targets) ─────


class HighlightOverlay(QWidget):
    """Transparent, mouse-passthrough overlay drawing an accent ring around each
    teaching target. Static targets get a thin steady ring; the active beat's
    target gets a thicker, gently pulsing ring with a soft outer glow.

    No screen dim (per the chosen approach) — the live UI stays fully readable.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("coachmarkOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._statics: list[QWidget] = []
        self._active: QWidget | None = None
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def set_targets(self, widgets: list[QWidget]) -> None:
        self._statics = [w for w in widgets if w is not None]
        self.update()

    def set_active(self, widget: QWidget | None) -> None:
        self._active = widget
        if widget is not None and not self._timer.isActive():
            self._timer.start()
        elif widget is None and self._timer.isActive():
            self._timer.stop()
        self.update()

    def clear(self) -> None:
        self._statics = []
        self.set_active(None)

    def _tick(self) -> None:
        self._phase += 0.12
        self.update()

    def _rect_for(self, w: QWidget, pad: int) -> QRect:
        top_left = w.mapTo(self.parentWidget(), QPoint(0, 0))
        return QRect(top_left, w.size()).adjusted(-pad, -pad, pad, pad)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt override)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(Qt.BrushStyle.NoBrush)

        for w in self._statics:
            if w is self._active or not w.isVisible():
                continue
            pen = QPen(QColor(0, 229, 204, 110))
            pen.setWidth(2)
            p.setPen(pen)
            p.drawRoundedRect(self._rect_for(w, 5), 8, 8)

        if self._active is not None and self._active.isVisible():
            pulse = 0.5 + 0.5 * math.sin(self._phase)  # 0..1
            r = self._rect_for(self._active, 6)
            for i, grow in enumerate((10, 6)):
                glow = QPen(QColor(0, 229, 204, int(30 + 50 * pulse) // (i + 1)))
                glow.setWidth(2)
                p.setPen(glow)
                p.drawRoundedRect(r.adjusted(-grow, -grow, grow, grow), 12, 12)
            ring = QPen(QColor(0, 229, 204, int(200 + 55 * pulse)))
            ring.setWidth(3)
            p.setPen(ring)
            p.drawRoundedRect(r, 9, 9)


# ── Controller: drives the beat sequence over the live MainWindow ────────────


class CoachmarkController(QObject):
    """Drives the first-run coachmark tour over the live ``MainWindow``.

    Resolves each beat's target from the real widgets (``_run_button``, a live
    Dashboard quick-fix button, ``_revert_button``), positions the bubble + active
    ring, and advances / dismisses on user input. ``W`` is handled by the app's
    global ``WASDInputFilter`` (the active bubble's ``next_btn`` is made the sole
    default button); ``Esc`` and clicks outside the bubble are handled by an event
    filter installed on the QApplication only while the tour is active.

    On dismissal the static rings clear but the hover tooltips remain, so the
    taught controls keep teaching after the first run.
    """

    def __init__(self, main, settings=None, parent=None) -> None:
        super().__init__(parent or main)
        self._main = main
        self._settings = settings
        self._stage: QWidget = main.centralWidget()
        self._overlay = HighlightOverlay(self._stage)
        self._overlay.setGeometry(self._stage.rect())
        self._overlay.hide()

        self._bubble: CoachmarkBubble | None = None
        self._index = -1
        self._targets: dict[str, QWidget] = {}
        self._scheduled = False
        self._filter_installed = False
        self._saved_defaults: list[QPushButton] = []
        self._active_default: QPushButton | None = None

        # Persistent hover tooltips on the always-present sidebar controls. The
        # quick-fix button's tooltip is set per-run in _resolve_targets (it's a
        # dynamic card). Existing per-finding status-label tooltips are untouched.
        self._set_hover(getattr(main, "_run_button", None), "optimize")
        self._set_hover(getattr(main, "_revert_button", None), "revert")

        # Re-anchor on window resize/move; dismiss when the user leaves the
        # Dashboard view (the fix target lives there).
        self._main.installEventFilter(self)
        content = getattr(main, "_content", None)
        if content is not None and hasattr(content, "currentChanged"):
            content.currentChanged.connect(self._on_view_changed)

    # ── public API ──────────────────────────────────────────────────────

    def schedule_first_run(self) -> None:
        """Schedule the one-time first-run tour (no-op if already seen/scheduled).

        Call from a site that runs inside ``app.exec()`` (``MainWindow.showEvent``
        on the first show) — never from inside ``splash.exec()``, or the bundled
        exe drops the QTimer (see ``scroll_hint.py`` /
        ``feedback_pyside_nested_loop_qtimer``).
        """
        if self._scheduled:
            return
        if self._settings is not None and self._settings.has_seen_coachmarks():
            return
        self._scheduled = True
        self._first_run_attempts = 0
        QTimer.singleShot(_SETTLE_MS, self._start_first_run)

    def _start_first_run(self) -> None:
        if self._settings is not None and self._settings.has_seen_coachmarks():
            return
        # Wait until the dashboard's quick-fix cards have been wired so the "fix"
        # beat can anchor a live card. The fast startup path wires them
        # synchronously before this timer fires; the slow path (orchestrator still
        # finishing after the window shows) wires them later, so poll a few times,
        # then show regardless so the tour never stalls.
        dash = getattr(self._main, "_dashboard", None)
        ready = (
            dash is None
            or not hasattr(dash, "is_coachmark_ready")
            or dash.is_coachmark_ready()
        )
        if not ready and self._first_run_attempts < _MAX_FIRST_RUN_ATTEMPTS:
            self._first_run_attempts += 1
            QTimer.singleShot(_RETRY_MS, self._start_first_run)
            return
        self.start()

    def start(self) -> None:
        """Show the tour from the first beat (replay-safe — ignores the seen flag).

        If a tour is already running (e.g. Help pressed mid-tour), fully tear it
        down first so default-button bookkeeping and the event filter don't stack.
        """
        if self._index >= 0 or self._bubble is not None:
            self.dismiss()
        self._resolve_targets()
        self._overlay.setGeometry(self._stage.rect())
        self._overlay.set_targets(list(self._targets.values()))
        self._overlay.show()
        self._overlay.raise_()
        self._capture_existing_defaults()
        self._install_filter()
        self._index = 0
        self._show_beat()

    def dismiss(self) -> None:
        """Tear down the tour, restore default-button ownership, mark it seen."""
        if self._index < 0 and self._bubble is None:
            return
        self._index = -1
        self._teardown_bubble()
        self._overlay.clear()
        self._overlay.hide()
        self._restore_defaults()
        self._remove_filter()
        if self._settings is not None:
            self._settings.mark_coachmarks_seen()

    def next(self) -> None:
        if self._index < 0:
            return
        self._index += 1
        if self._index >= len(BEATS):
            self.dismiss()
        else:
            self._show_beat()

    # ── target resolution ───────────────────────────────────────────────

    def _resolve_targets(self) -> None:
        main = self._main
        targets: dict[str, QWidget] = {}

        run_btn = getattr(main, "_run_button", None)
        if run_btn is not None:
            targets["optimize"] = run_btn

        # Live quick-fix button (Fix Now / Apply / Optimize) if any is visible,
        # else fall back to the always-present Mouse Polling card -- a real
        # per-card action -- so the beat anchors on a card the user can act on,
        # never a stat tile (which has no Fix button and made the "Hit Fix Now"
        # copy point at nothing).
        dash = getattr(main, "_dashboard", None)
        fix_target = None
        if dash is not None and hasattr(dash, "coachmark_fix_target"):
            fix_target = dash.coachmark_fix_target()
        if fix_target is not None:
            self._set_hover(fix_target, "fix")
        elif dash is not None and hasattr(dash, "coachmark_fix_fallback"):
            fix_target = dash.coachmark_fix_fallback()
        if fix_target is not None:
            targets["fix"] = fix_target

        revert_btn = getattr(main, "_revert_button", None)
        if revert_btn is not None:
            targets["revert"] = revert_btn

        self._targets = targets

    def _set_hover(self, widget, beat_name: str) -> None:
        if widget is None:
            return
        beat = _BEAT_BY_NAME.get(beat_name)
        if beat is not None:
            widget.setToolTip(tooltip_html(beat["title"], beat["body"]))

    def _ordered_beats(self) -> list[dict[str, str]]:
        """Beats whose target resolved this run (skips e.g. fix on an empty dash)."""
        return [b for b in BEATS if b["name"] in self._targets]

    # ── beat rendering ──────────────────────────────────────────────────

    def _show_beat(self) -> None:
        beats = self._ordered_beats()
        if self._index >= len(beats):
            self.dismiss()
            return
        beat = beats[self._index]
        target = self._targets[beat["name"]]
        self._overlay.set_active(target)
        self._overlay.raise_()

        self._teardown_bubble()
        self._bubble = CoachmarkBubble(
            beat["title"], beat["body"], beat["side"],
            on_next=self.next, on_skip=self.dismiss,
            last=(self._index == len(beats) - 1), parent=self._stage,
        )
        self._bubble.show()
        self._position_bubble(beat, target)
        # C-reuse: make this bubble's Next button the sole default so the global
        # WASDInputFilter's W clicks it.
        self._set_active_default(self._bubble.next_btn)

    def reposition(self) -> None:
        if self._bubble is None or self._index < 0:
            return
        beats = self._ordered_beats()
        if self._index < len(beats):
            beat = beats[self._index]
            target = self._targets.get(beat["name"])
            if target is not None:
                self._position_bubble(beat, target)
        self._overlay.setGeometry(self._stage.rect())
        self._overlay.update()

    def _position_bubble(self, beat: dict[str, str], target: QWidget) -> None:
        b = self._bubble
        assert b is not None
        b.adjustSize()
        bw, bh = b.width(), b.height()
        side = beat["side"]

        tl = target.mapTo(self._stage, QPoint(0, 0))
        tr = QRect(tl, target.size())

        if side == "right":
            x = tr.right() + GAP - GLOW
            y = tr.center().y() - bh // 2
        elif side == "left":
            x = tr.left() - GAP - bw + GLOW
            y = tr.center().y() - bh // 2
        elif side == "top":
            x = tr.center().x() - bw // 2
            y = tr.top() - GAP - bh + GLOW
        else:  # bottom
            x = tr.center().x() - bw // 2
            y = tr.bottom() + GAP - GLOW

        m = 6
        x = max(m, min(self._stage.width() - bw - m, x))
        y = max(m, min(self._stage.height() - bh - m, y))
        b.move(x, y)

        if side in ("right", "left"):
            b.set_arrow_pos(tr.center().y() - y)
        else:
            b.set_arrow_pos(tr.center().x() - x)
        b.raise_()

    # ── default-button ownership (C-reuse determinism guard) ─────────────

    def _capture_existing_defaults(self) -> None:
        """Record + clear any pre-existing default button so W is deterministic."""
        self._saved_defaults = []
        for btn in self._main.findChildren(QPushButton):
            if btn.isDefault():
                self._saved_defaults.append(btn)
                btn.setDefault(False)

    def _set_active_default(self, button: QPushButton) -> None:
        if self._active_default is not None:
            try:
                self._active_default.setDefault(False)
            except RuntimeError:
                pass  # previous bubble's button already deleted
        button.setDefault(True)
        button.setAutoDefault(True)
        self._active_default = button

    def _restore_defaults(self) -> None:
        if self._active_default is not None:
            try:
                self._active_default.setDefault(False)
            except RuntimeError:
                pass
            self._active_default = None
        for btn in self._saved_defaults:
            try:
                btn.setDefault(True)
            except RuntimeError:
                pass
        self._saved_defaults = []

    # ── input handling (Esc + click-outside) ────────────────────────────

    def _install_filter(self) -> None:
        if self._filter_installed:
            return
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
            self._filter_installed = True

    def _remove_filter(self) -> None:
        if not self._filter_installed:
            return
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self._filter_installed = False

    def eventFilter(self, obj, event):  # noqa: N802 (Qt override)
        etype = event.type()
        # MainWindow resize/move → re-anchor the active bubble + overlay.
        if obj is self._main and etype in (QEvent.Type.Resize, QEvent.Type.Move):
            self.reposition()
            return False
        if self._index < 0:
            return False
        if etype == QEvent.Type.KeyPress and event.key() in (
            Qt.Key.Key_Escape, Qt.Key.Key_S,
        ):
            # Esc or S dismisses (S = Skip, mirroring the bubble's Skip (S) button
            # and the app-wide WASD convention W=proceed / S=back). Consume it so
            # it doesn't reach the main-window Esc shortcut or the WASDInputFilter's
            # (no-op-while-idle) stop path while the tour is running.
            self.dismiss()
            return True
        if etype == QEvent.Type.MouseButtonPress and self._bubble is not None:
            # A click anywhere outside the bubble dismisses the tour (and is left
            # to propagate, so clicking the highlighted control still works).
            if not _is_descendant(obj, self._bubble):
                self.dismiss()
        return False

    def _on_view_changed(self, _index: int) -> None:
        if self._index >= 0:
            self.dismiss()

    # ── teardown ─────────────────────────────────────────────────────────

    def _teardown_bubble(self) -> None:
        if self._bubble is not None:
            self._bubble.hide()
            self._bubble.deleteLater()
            self._bubble = None
