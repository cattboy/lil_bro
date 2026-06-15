"""Pipeline output view — the page shown during/after an optimization run.

A pure layout container: header (title + phase pill), live CPU/GPU/RAM
stats, the Cinebench benchmark row, a progress bar, and the scrolling
log panel. ``MainWindow`` stacks it next to the Dashboard and re-exports
the sub-widgets that ``app.py`` drives.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class OutputView(QWidget):
    """Pipeline output page. Sub-widgets are exposed as attributes.

    ``_output_panel``, ``_benchmark_row``, ``_progress_bar``,
    ``_progress_label``, ``_live_stat_row`` and ``_output_title`` are read
    by ``MainWindow`` and ``app.py`` after
    construction — keep these attribute names stable.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        from src.gui.widgets.output_panel import OutputPanel
        from src.gui.widgets.benchmark_row import BenchmarkRow, LiveStatRow

        self.setObjectName("outputView")

        output_layout = QVBoxLayout(self)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)

        # Header row
        output_header = QFrame()
        output_header.setObjectName("outputHeader")
        hdr_row = QHBoxLayout(output_header)
        hdr_row.setContentsMargins(20, 12, 20, 12)

        self._output_title = QLabel("Pipeline")
        self._output_title.setObjectName("outputTitle")
        hdr_row.addWidget(self._output_title)
        hdr_row.addStretch()

        output_layout.addWidget(output_header)

        # Live system stats — realtime CPU/GPU/RAM cards, updated while
        # (and after) the pipeline runs by LiveStatRow's own poll thread.
        self._live_stat_row = LiveStatRow()
        output_layout.addWidget(self._live_stat_row)

        # Benchmark score row
        self._benchmark_row = BenchmarkRow()
        output_layout.addWidget(self._benchmark_row)

        # Progress bar (hidden until pipeline emits progress_changed)
        self._progress_label = QLabel("")
        self._progress_label.setObjectName("progressLabel")
        self._progress_label.setVisible(False)
        self._progress_label.setContentsMargins(20, 4, 20, 0)
        output_layout.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setAccessibleName("Pipeline progress")
        self._progress_bar.setVisible(False)
        self._progress_bar.setContentsMargins(20, 0, 20, 0)
        output_layout.addWidget(self._progress_bar)

        # Output panel with toolbar
        self._output_panel = OutputPanel()
        output_layout.addWidget(self._output_panel, stretch=1)
