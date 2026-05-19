from src.gui.widgets.benchmark_row import BenchmarkRow


def test_benchmark_row_starts_pending(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    assert row._status._value.text() == "PENDING"
    assert row._baseline._value.text() == "—"
    assert row._postopt._value.text() == "—"
    assert row._delta._value.text() == "—"
    assert row._cpu_peak._value.text() == "—"


def test_benchmark_row_reset_clears_state(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    row.set_baseline({"CPU_Single": "250.00 pts"}, 72.3)
    row.reset()
    assert row._baseline._value.text() == "—"
    assert row._status._value.text() == "PENDING"
    assert row._baseline_pts is None


def test_set_baseline_fills_cards(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    row.set_baseline({"CPU_Single": "247.39 pts"}, 71.5)
    assert row._baseline._value.text() == "247.39 pts"
    assert row._cpu_peak._value.text() == "71.5 °C"
    assert row._status._value.text() == "Running"
    assert row._baseline_pts == 247.39


def test_set_baseline_missing_score_is_safe(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    row.set_baseline({}, None)
    assert row._baseline._value.text() == "—"
    assert row._cpu_peak._value.text() == "—"
    assert row._status._value.text() == "Running"


def test_set_final_fills_postopt_and_computes_delta(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    row.set_baseline({"CPU_Single": "200.00 pts"}, None)
    row.set_final({"CPU_Single": "210.00 pts"})
    assert row._postopt._value.text() == "210.00 pts"
    assert row._status._value.text() == "Running"  # reverts to Running after Cinebench completes
    assert row._delta._value.text() == "+5.0%"


def test_negative_delta_shown_correctly(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    row.set_baseline({"CPU_Single": "210.00 pts"}, None)
    row.set_final({"CPU_Single": "200.00 pts"})
    assert row._delta._value.text() == "-4.8%"


def test_delta_skipped_when_baseline_missing(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    row.set_final({"CPU_Single": "200.00 pts"})
    assert row._delta._value.text() == "—"


def test_benchmark_row_accessible_name(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    assert row.accessibleName() == "Benchmark scores"


def test_pipeline_running_sets_status(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    row.set_pipeline_running()
    assert row._status._value.text() == "Running"


def test_pipeline_complete_sets_status(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    row.set_pipeline_complete()
    assert row._status._value.text() == "Complete"


def test_pipeline_failed_sets_status(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    row.set_pipeline_failed()
    assert row._status._value.text() == "Failed"


def test_set_benchmark_started_sets_status(qtbot):
    row = BenchmarkRow()
    qtbot.addWidget(row)
    row.set_benchmark_started()
    assert row._status._value.text() == "Benchmarking"
