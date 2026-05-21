"""Mouse polling-rate card for the dashboard.

A self-contained widget: shows the last-measured USB polling rate and a
"Test Polling" button that runs a fresh ~2-second measurement on a
background QThread. Once the user runs a manual test, the periodic
system-stats snapshot stops overwriting the displayed value.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.gui.theme import repolish


class MousePollCard(QFrame):
    """USB mouse polling-rate card with an on-demand measurement button."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("pollWidget")
        self.setAccessibleName("Mouse polling rate")

        poll_h = QHBoxLayout(self)
        poll_h.setContentsMargins(20, 16, 20, 16)

        poll_left = QVBoxLayout()
        poll_left.setSpacing(4)

        poll_label = QLabel("MOUSE POLLING")
        poll_label.setObjectName("pollLabel")
        poll_left.addWidget(poll_label)

        hz_row = QHBoxLayout()
        hz_row.setSpacing(4)
        self._poll_val = QLabel("—")
        self._poll_val.setObjectName("pollValue")
        self._poll_unit = QLabel("Hz")
        self._poll_unit.setObjectName("pollUnit")
        hz_row.addWidget(self._poll_val)
        hz_row.addWidget(self._poll_unit)
        hz_row.addStretch()
        poll_left.addLayout(hz_row)

        self._poll_status = QLabel("Not measured")
        self._poll_status.setObjectName("pollStatus")
        poll_left.addWidget(self._poll_status)

        poll_h.addLayout(poll_left)
        poll_h.addStretch()

        self._poll_btn = QPushButton("Test Polling")
        self._poll_btn.setObjectName("secondary")
        self._poll_btn.setFixedWidth(120)
        self._poll_btn.clicked.connect(self._manual_poll)
        poll_h.addWidget(self._poll_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Background QThread holders for the manual mouse-poll dispatch.
        # check_polling_rate() blocks for ~2s, so it cannot run on the
        # GUI thread. Reentry-guarded in _manual_poll().
        self._mouse_poll_thread: QThread | None = None
        self._mouse_poll_worker = None
        # Once a manual measurement has run, the periodic snapshot tick
        # must not clobber the result with "Not measured" (the quick-status
        # fallback when no live measurement is available).
        self._mouse_manually_measured: bool = False

    # ── Public API ─────────────────────────────────────────────────────

    def apply_snapshot(self, snapshot: dict) -> None:
        """Render the cached mouse-Hz carried by a periodic poll snapshot.

        Only applied *before* the first manual measurement — a real
        "Test Polling" run is authoritative and must not be clobbered by
        the quick-status fallback the periodic tick carries.
        """
        if self._mouse_manually_measured:
            return
        hz_str = snapshot.get("mouse_hz", "")
        if hz_str and hz_str not in ("—", "Not measured"):
            self._update_poll_display(hz_str)

    # ── Internal ───────────────────────────────────────────────────────

    def _manual_poll(self) -> None:
        """Dispatch ``check_polling_rate()`` on a background QThread.

        The probe blocks ~2s sampling cursor deltas — calling it on the
        GUI thread would freeze the dashboard. Reentry-guarded so rapid
        button clicks don't spawn multiple workers.
        """
        from src.utils.debug_logger import get_debug_logger
        log = get_debug_logger()

        if self._mouse_poll_thread is not None:
            log.info("MousePollCard._manual_poll: already running, ignoring click")
            return

        log.info("MousePollCard._manual_poll: dispatching MousePollWorker")
        self._poll_btn.setEnabled(False)
        self._poll_status.setText("Measuring (2s)… MOVE YOUR MOUSE AROUND!")
        self._poll_status.setToolTip("")
        # Clear any prior sev so "Measuring…" doesn't inherit the stale
        # coral/amber/mint of the previous result — would read as a tier
        # indicator that no longer reflects the truth.
        self._set_poll_sev("")

        from src.gui.worker import _MousePollWorker
        thread = QThread(self)
        thread.setObjectName("MousePoll")
        worker = _MousePollWorker()
        worker.moveToThread(thread)

        def _on_mouse_done(result: dict) -> None:
            from src.llm.action_proposer import propose_for_check
            hz = int(result.get("current_hz", 0) or 0)
            status = result.get("status", "OK")
            log.info(
                "MousePollCard._manual_poll: result hz=%d status=%s",
                hz, status,
            )

            self._mouse_manually_measured = True
            self._poll_val.setText(str(hz) if hz else "—")
            if status == "ERROR":
                self._poll_status.setText("Measurement failed")
                self._poll_status.setToolTip("")
                _sev = "high"
            elif hz >= 1000:
                self._poll_status.setText("Excellent — optimal for gaming")
                self._poll_status.setToolTip("")
                _sev = "low"
            elif hz >= 500:
                self._poll_status.setText("Acceptable — 1000Hz preferred")
                self._poll_status.setToolTip("")
                _sev = "medium"
            else:
                # FAIL tier — canonical text from FALLBACK_PROPOSALS, full
                # explanation on hover. OK tiers above keep their live
                # commentary (no FAIL → no template, by design).
                proposal = propose_for_check(
                    "mouse_polling",
                    {"current_hz": hz, "threshold_hz": 500},
                )
                self._poll_status.setText(proposal["proposed_action"])
                self._poll_status.setToolTip(proposal["explanation"])
                _sev = "high"
            self._set_poll_sev(_sev)

            self._poll_btn.setEnabled(True)
            thread.quit()

        worker.finished.connect(_on_mouse_done)
        thread.started.connect(worker.run)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: setattr(self, "_mouse_poll_thread", None))
        thread.finished.connect(lambda: setattr(self, "_mouse_poll_worker", None))

        self._mouse_poll_thread = thread
        self._mouse_poll_worker = worker
        thread.start()

    def _set_poll_sev(self, sev: str) -> None:
        """Set severity tone on the mouse-poll Hz value AND status label.

        Both labels use objectNames `pollValue` / `pollStatus` which have
        `[sev="low|medium|high"]` QSS rules in theme.py. Re-polish both
        unconditionally so attribute selectors re-evaluate.

        sev: "low" (mint) | "medium" (amber) | "high" (coral) | "" (neutral)
        """
        self._poll_val.setProperty("sev", sev)
        self._poll_status.setProperty("sev", sev)
        repolish(self._poll_val)
        repolish(self._poll_status)

    def _update_poll_display(self, hz_str: str) -> None:
        from src.llm.action_proposer import propose_for_check
        try:
            hz = int(float(hz_str.replace(" Hz", "").replace("Hz", "")))
            self._poll_val.setText(str(hz))
            if hz >= 1000:
                self._poll_status.setText("Excellent")
                self._poll_status.setToolTip("")
                _sev = "low"
            elif hz >= 500:
                self._poll_status.setText("Good")
                self._poll_status.setToolTip("")
                _sev = "medium"
            else:
                # FAIL tier — pull canonical text from FALLBACK_PROPOSALS
                # (single source of truth shared with pipeline approval flow).
                proposal = propose_for_check(
                    "mouse_polling",
                    {"current_hz": hz, "threshold_hz": 500},
                )
                self._poll_status.setText(proposal["proposed_action"])
                self._poll_status.setToolTip(proposal["explanation"])
                _sev = "high"
            self._set_poll_sev(_sev)
        except (ValueError, AttributeError):
            self._poll_val.setText("—")
            self._poll_status.setText("Not measured")
            self._poll_status.setToolTip("")
            self._set_poll_sev("")
