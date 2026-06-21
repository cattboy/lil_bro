"""Developer-only mock of the first-run coachmarks onboarding.

A quick, self-contained visual prototype for the FAQ-Instructions design
(`cattboy-FAQ-Instructions-design-20260617-134435.md`): in-context arrow-bubble
callouts that float over the *real* Dashboard chrome and point at the actual
controls a first-timer will press — `Start Optimization`, a quick-fix card, and
`Revert Changes`. Each target gets a pulsing accent highlight ring, and the same
copy is wired as an always-on hover tooltip, so the teaching persists past run
one. This is the dev sandbox for tuning bubble copy + placement BEFORE the real
`src/gui/widgets/coachmarks.py` controller is built and wired into the live
StartupCoordinator.

NOT bundled (no lil_bro.spec entry). Reuses the production theme so the sidebar,
brand mark, and cards render exactly like the app, but the window/cards here are
a lightweight representative stand-in — not the live MainWindow + Dashboard.

Run from the repo root (venv active):

    python scripts/mock_coachmarks.py            # interactive walkthrough
    python scripts/mock_coachmarks.py --smoke    # headless anchor/advance check

Controls (interactive):
    W / → / Space / Enter   advance to the next beat (or the bubble's Next button)
    S / Esc                 dismiss the tour (or the bubble's Skip button)
    H                       replay the whole tour from the top
    hover any glowing control to see its tooltip (persists after the tour)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # CWD-relative paths behave like the real app

import io
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(errors="replace")

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui import theme

C = theme.COLORS
F = theme.FONTS

# ── Bubble geometry constants ───────────────────────────────────────────────
BUBBLE_W = 332      # total widget width (incl. glow + arrow margins)
GLOW = 16           # outer margin reserved so the drop-shadow glow has room
PAD = 16            # inner text padding inside the body rect
ARROW = 12          # arrow depth (also the body inset on the arrow edge)
ARROW_HALF = 9      # arrow base half-width
RADIUS = 10         # body corner radius
GAP = 8             # gap between the target and the arrow tip

_OPPOSITE = {"right": "left", "left": "right", "top": "bottom", "bottom": "top"}


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
            "One click and lil_bro scans your whole rig, then fixes everything "
            "dragging your FPS down. It snaps a restore point first and you OK "
            "every change — so go ahead and YOLO it, nothing touches your PC "
            "without your say-so."
        ),
    },
    {
        "name": "fix",
        "side": "bottom",
        "title": "Quick fixes",
        "body": (
            "Already spotted a problem? Hit <b>Fix Now</b> to apply just this one "
            "change on the spot — no need to run the whole optimization pass."
        ),
    },
    {
        "name": "revert",
        "side": "right",
        "title": "Revert Changes",
        "body": (
            "Changed your mind? One click rolls back everything lil_bro did this "
            "session — your restore point is the safety net sitting behind it."
        ),
    },
]


def tooltip_html(title: str, body: str) -> str:
    """The same copy a beat shows, formatted for an always-on hover tooltip."""
    return (
        f"<div style='max-width:280px'>"
        f"<b style='color:{C['accent']}'>{title}</b><br>{body}</div>"
    )


# ── Arrow-bubble callout ────────────────────────────────────────────────────


class CoachmarkBubble(QWidget):
    """Frameless, brand-styled callout: a title + wrapped body + WASD buttons,
    with a directional arrow drawn toward its target.

    Painted entirely in ``paintEvent`` (rounded body + united arrow triangle)
    over a translucent background, with an accent drop-shadow glow. The arrow
    edge is the side *opposite* to where the bubble sits relative to its target.
    """

    def __init__(self, title: str, body: str, side: str,
                 on_next, on_skip, last: bool, parent: QWidget) -> None:
        super().__init__(parent)
        self.side = side
        self.arrow_edge = _OPPOSITE[side]
        self._arrow_pos: float | None = None  # along-edge coord (body-local)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
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
        title_lbl.setStyleSheet(
            f"color:{C['accent']}; font-family:'{F['mono']}'; font-size:13px;"
            f"font-weight:700; letter-spacing:0.04em;"
        )
        lay.addWidget(title_lbl)

        body_lbl = QLabel(body)
        body_lbl.setWordWrap(True)
        body_lbl.setTextFormat(Qt.TextFormat.RichText)
        body_lbl.setStyleSheet(
            f"color:{C['text_primary']}; font-family:'{F['sans']}'; font-size:13px;"
        )
        lay.addWidget(body_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch(1)
        skip = QPushButton("Skip (S)")
        skip.setObjectName("secondary")
        skip.setCursor(Qt.CursorShape.PointingHandCursor)
        skip.clicked.connect(on_skip)
        btn_row.addWidget(skip)
        nxt = QPushButton("Done (W)" if last else "Next (W)")
        nxt.setObjectName("primary")
        nxt.setCursor(Qt.CursorShape.PointingHandCursor)
        nxt.clicked.connect(on_next)
        btn_row.addWidget(nxt)
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

        p.fillPath(full, QBrush(QColor(C["elevated"])))
        pen = QPen(QColor(C["accent"]))
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
        self._statics = list(widgets)
        self.update()

    def set_active(self, widget: QWidget | None) -> None:
        self._active = widget
        if widget is not None and not self._timer.isActive():
            self._timer.start()
        elif widget is None and self._timer.isActive():
            self._timer.stop()
        self.update()

    def _tick(self) -> None:
        self._phase += 0.12
        self.update()

    def _rect_for(self, w: QWidget, pad: int) -> QRect:
        top_left = w.mapTo(self.parentWidget(), QPoint(0, 0))
        return QRect(top_left, w.size()).adjusted(-pad, -pad, pad, pad)

    def paintEvent(self, _event) -> None:  # noqa: N802 (Qt override)
        import math

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
            # Soft outer glow — a couple of faint expanding strokes.
            for i, grow in enumerate((10, 6)):
                glow = QPen(QColor(0, 229, 204, int(30 + 50 * pulse) // (i + 1)))
                glow.setWidth(2)
                p.setPen(glow)
                p.drawRoundedRect(r.adjusted(-grow, -grow, grow, grow), 12, 12)
            ring = QPen(QColor(0, 229, 204, int(200 + 55 * pulse)))
            ring.setWidth(3)
            p.setPen(ring)
            p.drawRoundedRect(r, 9, 9)


# ── Controller: ordered beats over the targets ──────────────────────────────


class CoachmarkController:
    """Drives the beat sequence: positions the bubble adjacent to each target,
    moves the overlay's active ring, and advances / dismisses on user input.
    On dismissal the static rings + hover tooltips remain, so the highlighted,
    hoverable fields keep teaching after the first run.
    """

    def __init__(self, stage: QWidget, overlay: HighlightOverlay,
                 targets: dict[str, QWidget], footer: QLabel) -> None:
        self.stage = stage
        self.overlay = overlay
        self.targets = targets
        self.footer = footer
        self._bubble: CoachmarkBubble | None = None
        self._index = -1

    # ── lifecycle ───────────────────────────────────────────────────────
    def start(self) -> None:
        self.overlay.set_targets(list(self.targets.values()))
        self.overlay.raise_()
        self._index = 0
        self._show_beat()

    def next(self) -> None:
        if self._index < 0:
            return
        self._index += 1
        if self._index >= len(BEATS):
            self.dismiss()
        else:
            self._show_beat()

    def dismiss(self) -> None:
        self._index = -1
        self.overlay.set_active(None)
        if self._bubble is not None:
            self._bubble.hide()
            self._bubble.deleteLater()
            self._bubble = None
        self.footer.setText(
            "  Tour dismissed — hover any glowing control for its tip"
            "    ·    (H) replay the tour"
        )

    # ── beat rendering ──────────────────────────────────────────────────
    def _show_beat(self) -> None:
        beat = BEATS[self._index]
        target = self.targets[beat["name"]]
        self.overlay.set_active(target)

        if self._bubble is not None:
            self._bubble.hide()
            self._bubble.deleteLater()
        self._bubble = CoachmarkBubble(
            beat["title"], beat["body"], beat["side"],
            on_next=self.next, on_skip=self.dismiss,
            last=(self._index == len(BEATS) - 1), parent=self.stage,
        )
        self._bubble.show()
        self._position_bubble()
        self.footer.setText(
            f"  Beat {self._index + 1} of {len(BEATS)}"
            "    ·    (W) Next    ·    (S)/Esc Skip    ·    (H) Replay"
            "    ·    hover any glowing control for its tip"
        )

    def reposition(self) -> None:
        if self._bubble is not None:
            self._position_bubble()
        self.overlay.update()

    def _position_bubble(self) -> None:
        assert self._bubble is not None
        beat = BEATS[self._index]
        target = self.targets[beat["name"]]
        side = beat["side"]
        b = self._bubble
        b.adjustSize()
        bw, bh = b.width(), b.height()

        tl = target.mapTo(self.stage, QPoint(0, 0))
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
        x = max(m, min(self.stage.width() - bw - m, x))
        y = max(m, min(self.stage.height() - bh - m, y))
        b.move(x, y)

        # Re-aim the arrow at the target's center after edge-clamping.
        if side in ("right", "left"):
            b.set_arrow_pos(tr.center().y() - y)
        else:
            b.set_arrow_pos(tr.center().x() - x)
        b.raise_()


# ── Representative window (sidebar + cards, real theme) ──────────────────────


def _nav_btn(label: str, *, accent: bool = False, state: str = "") -> QPushButton:
    btn = QPushButton(label)
    btn.setProperty("navRole", "nav")
    btn.setProperty("navState", state if state else ("active" if accent else ""))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFlat(True)
    btn.setMinimumHeight(36)
    return btn


def _fix_card(title: str, status: str, sev: str, action: str) -> tuple[QFrame, QPushButton]:
    card = QFrame()
    card.setObjectName("pollWidget")
    col = QVBoxLayout(card)
    col.setContentsMargins(16, 14, 16, 14)
    col.setSpacing(8)

    lbl = QLabel(title.upper())
    lbl.setObjectName("pollLabel")
    col.addWidget(lbl)

    st = QLabel(status)
    st.setObjectName("pollStatus")
    st.setProperty("sev", sev)
    st.setWordWrap(True)
    col.addWidget(st)

    row = QHBoxLayout()
    row.addStretch(1)
    btn = QPushButton(action)
    btn.setObjectName("primary")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    row.addWidget(btn)
    col.addLayout(row)
    return card, btn


class MockWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("lil_bro — coachmarks mock")
        self.resize(1040, 680)

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        stage = QWidget()
        stage.setObjectName("stage")
        row = QHBoxLayout(stage)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self._build_sidebar())
        row.addWidget(self._build_content(), 1)
        outer.addWidget(stage, 1)

        self._footer = QLabel("  Loading the tour…")
        self._footer.setStyleSheet(
            f"background:{C['elevated']}; color:{C['text_secondary']};"
            f"font-family:'{F['mono']}'; font-size:11px; padding:8px 12px;"
            f"border-top:1px solid {C['border_default']};"
        )
        outer.addWidget(self._footer)

        self.setCentralWidget(central)
        self._stage = stage

        # Coachmark layer over the stage.
        self._overlay = HighlightOverlay(stage)
        self._overlay.setGeometry(stage.rect())
        targets = {
            "optimize": self._optimize_btn,
            "fix": self._fix_btn,
            "revert": self._revert_btn,
        }
        for name, w in targets.items():
            beat = next(b for b in BEATS if b["name"] == name)
            w.setToolTip(tooltip_html(beat["title"], beat["body"]))
        self._controller = CoachmarkController(stage, self._overlay, targets, self._footer)
        self._started = False

    # ── chrome builders ─────────────────────────────────────────────────
    def _build_sidebar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("sidebar")
        frame.setFixedWidth(220)
        col = QVBoxLayout(frame)
        col.setContentsMargins(0, 20, 0, 16)
        col.setSpacing(2)

        brand = QLabel(f'lil<span style="color: {C["accent"]};">_bro</span>')
        brand.setObjectName("sidebarBrand")
        brand.setTextFormat(Qt.TextFormat.RichText)
        col.addWidget(brand)

        self._optimize_btn = _nav_btn("▶  Start Optimization (2)", accent=True)
        col.addWidget(_nav_btn("◆  Dashboard (1)"))
        col.addWidget(self._optimize_btn)
        col.addStretch(1)

        divider = QFrame()
        divider.setObjectName("navDivider")
        divider.setFixedHeight(1)
        col.addWidget(divider)
        col.addSpacing(4)

        # "View Log" (action audit log) is always shown; "View Debug Log" is
        # --debug-only in the real sidebar (hidden by default there).
        col.addWidget(_nav_btn("📄  View Log", state="muted"))
        col.addWidget(_nav_btn("📄  View Debug Log", state="muted"))
        self._revert_btn = _nav_btn("↩  Revert Changes (R)", state="warning")
        col.addWidget(self._revert_btn)
        col.addWidget(_nav_btn("⚙  AI Setup (A)", state="muted"))
        col.addWidget(_nav_btn("?  Help / FAQ (H)", state="muted"))
        col.addWidget(_nav_btn("✕  Exit (E)", state="danger"))
        return frame

    def _build_content(self) -> QWidget:
        page = QWidget()
        col = QVBoxLayout(page)
        col.setContentsMargins(28, 24, 28, 24)
        col.setSpacing(16)

        head = QLabel("DASHBOARD")
        head.setStyleSheet(
            f"color:{C['text_primary']}; font-family:'{F['mono']}';"
            f"font-size:22px; font-weight:800; letter-spacing:0.04em;"
        )
        col.addWidget(head)
        sub = QLabel("Live stats and one-click fixes — no full run required.")
        sub.setStyleSheet(f"color:{C['text_secondary']}; font-family:'{F['sans']}'; font-size:13px;")
        col.addWidget(sub)
        col.addSpacing(4)

        power_card, self._fix_btn = _fix_card(
            "Power Plan", "Balanced — throttling your clocks mid-game.", "high", "Fix Now",
        )
        col.addWidget(power_card)

        disp_card, _ = _fix_card(
            "Display Refresh", "Running 60 Hz of an available 144 Hz.", "medium", "Set 144 Hz",
        )
        col.addWidget(disp_card)

        gpu_card, _ = _fix_card(
            "GPU Temp", "71°C under load — comfortable headroom.", "low", "Details",
        )
        col.addWidget(gpu_card)
        col.addStretch(1)
        return page

    # ── coachmark layer geometry + input ────────────────────────────────
    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        if not self._started:
            self._started = True
            QTimer.singleShot(180, self._controller.start)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self._overlay.setGeometry(self._stage.rect())
        self._controller.reposition()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        k = event.key()
        if k in (Qt.Key.Key_W, Qt.Key.Key_Right, Qt.Key.Key_Space,
                 Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._controller.next()
        elif k in (Qt.Key.Key_S, Qt.Key.Key_Escape):
            self._controller.dismiss()
        elif k == Qt.Key.Key_H:
            self._controller.start()
        else:
            super().keyPressEvent(event)


# ── Smoke test (anchors + advance + dismiss, safe offscreen) ─────────────────


def _run_smoke(app: QApplication, win: MockWindow) -> None:
    ctrl = win._controller
    overlay = win._overlay

    def step() -> None:
        ctrl.start()
        assert ctrl._bubble is not None, "bubble not created on start"
        assert overlay._active is win._optimize_btn, "first beat must anchor to Optimize"
        print(f"[smoke] beat 1: anchored to {overlay._active.text()!r}")

        ctrl.next()
        assert overlay._active is win._fix_btn, "second beat must anchor to Fix card"
        print(f"[smoke] beat 2: anchored to {overlay._active.text()!r}")

        ctrl.next()
        assert overlay._active is win._revert_btn, "third beat must anchor to Revert"
        print(f"[smoke] beat 3: anchored to {overlay._active.text()!r}")

        ctrl.next()  # past the last beat → auto-dismiss
        assert overlay._active is None, "active ring must clear on dismiss"
        assert len(overlay._statics) == 3, "static rings must persist after the tour"
        assert ctrl._bubble is None, "bubble must be torn down on dismiss"
        tip = win._optimize_btn.toolTip()
        assert "Start Optimization" in tip, "hover tooltip copy missing"
        print(f"[smoke] persisted: {len(overlay._statics)} static rings + hover tips")
        print("[smoke] OK")
        app.quit()

    QTimer.singleShot(0, step)


# ── Entry ────────────────────────────────────────────────────────────────────


def main() -> int:
    smoke = "--smoke" in sys.argv
    if smoke:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    QApplication.setApplicationName("lil_bro")
    QApplication.setOrganizationName("lil_bro")
    app = QApplication(sys.argv)

    theme.load_fonts()
    app.setStyleSheet(theme.build_stylesheet())

    win = MockWindow()
    win.show()

    if smoke:
        _run_smoke(app, win)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
