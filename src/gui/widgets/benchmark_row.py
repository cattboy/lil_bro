from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout


class _BenchmarkCard(QFrame):
    """Single metric card in the benchmark score row."""

    def __init__(self, label: str, sublabel: str = "", parent=None) -> None:
        super().__init__(parent)
        # Reuse phaseCard CSS (same slot in output view, same visual treatment)
        self.setObjectName("phaseCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)

        self._label = QLabel(label)
        self._label.setObjectName("phaseNum")  # 10px mono muted — label row

        self._sublabel = QLabel(sublabel)
        self._sublabel.setObjectName("phaseName")  # 12px mono bold — sublabel row

        self._value = QLabel("—")
        self._value.setObjectName("cardValue")  # 24px JetBrains Mono — score display

        layout.addWidget(self._label)
        layout.addWidget(self._sublabel)
        layout.addWidget(self._value)

    def set_value(self, value: str, tone: str = "norm") -> None:
        self._value.setText(value)
        self._value.setProperty("statTone", tone)
        self._value.style().unpolish(self._value)
        self._value.style().polish(self._value)


class BenchmarkRow(QFrame):
    """5-card strip showing Cinebench before/after scores in the output view.

    Replaces the inert PhaseRow. Updated live by benchmark_score_ready signals.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Reuse phaseRow CSS — same visual slot, same background/border treatment
        self.setObjectName("phaseRow")
        self.setAccessibleName("Benchmark scores")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        def _card(label: str, sub: str = "") -> _BenchmarkCard:
            c = _BenchmarkCard(label, sub, self)
            c.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            layout.addWidget(c)
            return c

        self._baseline = _card("BASELINE", "Single-Core")
        self._postopt = _card("POST-OPT", "Single-Core")
        self._delta = _card("DELTA", "vs Baseline")
        self._cpu_peak = _card("CPU PEAK", "During Benchmark")
        self._status = _card("STATUS")

        self._baseline_pts: float | None = None
        self._final_pts: float | None = None

        self.reset()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> None:
        for card in (self._baseline, self._postopt, self._delta, self._cpu_peak):
            card.set_value("—")
        self._status.set_value("PENDING")
        self._baseline_pts = None
        self._final_pts = None

    def set_baseline(self, scores: dict, cpu_peak: float | None) -> None:
        pts_str = scores.get("CPU_Single", "")
        if pts_str:
            self._baseline.set_value(pts_str, "cyan")
            try:
                self._baseline_pts = float(pts_str.split()[0])
            except (ValueError, IndexError):
                self._baseline_pts = None

        if cpu_peak is not None:
            self._cpu_peak.set_value(f"{cpu_peak:.1f} °C")

        self._status.set_value("Running", "cyan")
        self._update_delta()

    def set_final(self, scores: dict) -> None:
        pts_str = scores.get("CPU_Single", "")
        if pts_str:
            self._postopt.set_value(pts_str, "cyan")
            try:
                self._final_pts = float(pts_str.split()[0])
            except (ValueError, IndexError):
                self._final_pts = None

        self._status.set_value("Running", "cyan")
        self._update_delta()

    def set_pipeline_running(self) -> None:
        self._status.set_value("Running", "cyan")

    def set_benchmark_started(self) -> None:
        self._status.set_value("Benchmarking", "cyan")

    def set_pipeline_complete(self) -> None:
        self._status.set_value("Complete", "ok")

    def set_pipeline_failed(self) -> None:
        self._status.set_value("Failed", "warn")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _update_delta(self) -> None:
        if self._baseline_pts is None or self._final_pts is None or self._baseline_pts == 0:
            return
        delta_pct = (self._final_pts - self._baseline_pts) / self._baseline_pts * 100
        sign = "+" if delta_pct >= 0 else ""
        tone = "ok" if delta_pct >= 0 else "warn"
        self._delta.set_value(f"{sign}{delta_pct:.1f}%", tone)
