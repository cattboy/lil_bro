"""Tests for OutputView — the pipeline output page (src/gui/widgets/output_view.py).

A pure layout container whose contract is the set of sub-widgets it exposes as
attributes for ``MainWindow``/``app.py`` to drive (``_output_panel``,
``_benchmark_row``, ``_progress_bar``, ``_progress_label``, ``_live_stat_row``,
``_output_title``). Uses the offscreen Qt platform (conftest.py) + qtbot.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QProgressBar

from src.gui.widgets.benchmark_row import BenchmarkRow, LiveStatRow
from src.gui.widgets.output_panel import OutputPanel
from src.gui.widgets.output_view import OutputView


def test_constructs_with_object_name(qtbot):
    view = OutputView()
    qtbot.addWidget(view)
    assert view.objectName() == "outputView"


def test_exposes_subwidget_attributes_with_expected_types(qtbot):
    """The attribute contract MainWindow/app.py rely on — keep names stable."""
    view = OutputView()
    qtbot.addWidget(view)
    assert isinstance(view._output_panel, OutputPanel)
    assert isinstance(view._benchmark_row, BenchmarkRow)
    assert isinstance(view._live_stat_row, LiveStatRow)
    assert isinstance(view._progress_bar, QProgressBar)
    assert isinstance(view._progress_label, QLabel)
    assert isinstance(view._output_title, QLabel)


def test_default_title_text(qtbot):
    view = OutputView()
    qtbot.addWidget(view)
    assert view._output_title.text() == "Pipeline"
    assert view._output_title.objectName() == "outputTitle"


def test_progress_widgets_start_hidden(qtbot):
    """Progress bar + label stay hidden until the pipeline emits progress."""
    view = OutputView()
    qtbot.addWidget(view)
    assert view._progress_bar.isVisible() is False
    assert view._progress_label.isVisible() is False


def test_progress_bar_configured_range_and_value(qtbot):
    view = OutputView()
    qtbot.addWidget(view)
    assert view._progress_bar.minimum() == 0
    assert view._progress_bar.maximum() == 100
    assert view._progress_bar.value() == 0
    assert view._progress_bar.isTextVisible() is False


def test_output_panel_is_wired_and_functional(qtbot):
    """The embedded OutputPanel is live — appending shows up in its text."""
    view = OutputView()
    qtbot.addWidget(view)
    view._output_panel.append_line("hello from pipeline")
    assert "hello from pipeline" in view._output_panel._text.toPlainText()
    view._output_panel.clear_log()
    assert view._output_panel._text.toPlainText() == ""
