import pytest
from unittest.mock import patch, MagicMock

from src.benchmarks.cinebench import (
    BenchmarkRunner,
    find_cinebench,
    _CINEBENCH_SEARCH_PATHS,
)


# ── find_cinebench ────────────────────────────────────────────────────────────

@patch("src.benchmarks.cinebench.os.path.isfile")
def test_find_cinebench_found(mock_isfile):
    """Returns the first matching path."""
    mock_isfile.side_effect = lambda p: "bench-exe" in p
    result = find_cinebench()
    assert result is not None
    assert "Cinebench.exe" in result


@patch("src.benchmarks.cinebench.os.path.isfile", return_value=False)
def test_find_cinebench_not_found(mock_isfile):
    """Returns None when no path matches."""
    assert find_cinebench() is None


@patch("src.benchmarks.cinebench.os.path.isfile")
def test_find_cinebench_checks_all_paths(mock_isfile):
    """All search paths should be checked."""
    mock_isfile.return_value = False
    find_cinebench()
    assert mock_isfile.call_count == len(_CINEBENCH_SEARCH_PATHS)


# ── _stress_core ──────────────────────────────────────────────────────────────







# ── run_cpu_fallback ──────────────────────────────────────────────────────────







# ── BenchmarkRunner.__init__ ─────────────────────────────────────────────────

@patch("src.benchmarks.cinebench.find_cinebench", return_value=None)
def test_runner_no_cinebench(mock_find):
    """has_cinebench is False when Cinebench isn't found."""
    runner = BenchmarkRunner()
    assert runner.has_cinebench is False
    assert runner.cinebench_path is None


@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_runner_explicit_path(mock_isfile):
    """Explicit path is used when file exists."""
    runner = BenchmarkRunner(cinebench_path=r"C:\Custom\CB.exe")
    assert runner.has_cinebench is True
    assert runner.cinebench_path == r"C:\Custom\CB.exe"


@patch("src.benchmarks.cinebench.find_cinebench", return_value=r"C:\Found\CB.exe")
def test_runner_auto_discovery(mock_find):
    """Auto-discovers Cinebench when no explicit path given."""
    runner = BenchmarkRunner()
    assert runner.has_cinebench is True
    assert runner.cinebench_path == r"C:\Found\CB.exe"


# ── BenchmarkRunner.run_benchmark — Cinebench path ──────────────────────────

@patch("src.benchmarks.cinebench.prompt_approval", return_value=True)
@patch("src.benchmarks.cinebench.Path.read_text", return_value="Running Single CPU Render Test...\nCB 247.39 (0.00)\n")
@patch("src.benchmarks.cinebench.Path.write_text")
@patch("src.benchmarks.cinebench.Path.exists", return_value=True)
@patch("src.benchmarks.cinebench.subprocess.Popen")
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_cinebench_success(mock_isfile, mock_popen, mock_exists, mock_write, mock_read, mock_approve):
    """Cinebench runs and returns success with parsed CB score."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0
    mock_proc.communicate.return_value = (None, None)
    mock_popen.return_value = mock_proc

    runner = BenchmarkRunner(cinebench_path=r"C:\CB\Cinebench.exe")
    result = runner.run_benchmark(full_suite=False)

    assert result["status"] == "success"
    assert result["benchmark"] == "cinebench"
    assert result["scores"].get("CPU_Single") == "247.39 pts"


@patch("src.benchmarks.cinebench.prompt_approval", return_value=True)
@patch("src.benchmarks.cinebench.Path.read_text", return_value="Running Multi CPU Render Test...\nCB 15320.11 (0.00)\n")
@patch("src.benchmarks.cinebench.Path.write_text")
@patch("src.benchmarks.cinebench.Path.exists", return_value=True)
@patch("src.benchmarks.cinebench.subprocess.Popen")
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_cinebench_full_suite(mock_isfile, mock_popen, mock_exists, mock_write, mock_read, mock_approve):
    """full_suite=True passes AllTests flag and parses multi-core score."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0
    mock_proc.communicate.return_value = (None, None)
    mock_popen.return_value = mock_proc

    runner = BenchmarkRunner(cinebench_path=r"C:\CB\Cinebench.exe")
    result = runner.run_benchmark(full_suite=True)

    assert result["status"] == "success"
    assert result["scores"].get("CPU_Multi") == "15320.11 pts"
    # Verify AllTests flag used in the batch file written to disk
    write_calls = mock_write.call_args_list
    bat_call = next((c for c in write_calls if "g_CinebenchAllTests" in str(c)), None)
    assert bat_call is not None


@patch("src.benchmarks.cinebench.prompt_approval", return_value=True)
@patch("src.benchmarks.cinebench.Path.write_text")
@patch(
    "src.benchmarks.cinebench.subprocess.Popen",
    side_effect=Exception("crash"),
)
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_cinebench_error(mock_isfile, mock_popen, mock_write, mock_approve):
    """Cinebench crash → error result."""
    runner = BenchmarkRunner(cinebench_path=r"C:\CB\Cinebench.exe")
    result = runner.run_benchmark()
    assert result["status"] == "error"


@patch("src.benchmarks.cinebench.prompt_approval", return_value=False)
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_benchmark_user_declines(mock_isfile, mock_approve):
    """User declines the Y/N prompt → skipped result, Cinebench never launched."""
    runner = BenchmarkRunner(cinebench_path=r"C:\CB\Cinebench.exe")
    result = runner.run_benchmark()
    assert result["status"] == "skipped"
    assert result["benchmark"] == "cinebench"


# ── BenchmarkRunner.run_benchmark — fallback path ───────────────────────────







# ── _parse_output ─────────────────────────────────────────────────────────────

def test_parse_output_multi():
    output = (
        "Running Single CPU Render Test...\nCB 247.39 (0.00)\n"
        "Running Multi CPU Render Test...\nCB 15320.11 (0.00)\n"
    )
    scores = BenchmarkRunner._parse_output(output, full_suite=True)
    assert scores["CPU_Single"] == "247.39 pts"
    assert scores["CPU_Multi"] == "15320.11 pts"


def test_parse_output_single():
    output = "Running Single CPU Render Test...\nCB 247.39 (0.00)\n"
    scores = BenchmarkRunner._parse_output(output, full_suite=False)
    assert scores["CPU_Single"] == "247.39 pts"


def test_parse_output_empty():
    assert BenchmarkRunner._parse_output("no scores here\n") == {}

# ── run_benchmark — no Cinebench installed ────────────────────────────────────

@patch("src.benchmarks.cinebench.find_cinebench", return_value=None)
def test_run_benchmark_no_cinebench_skipped(mock_find):
    """When Cinebench is missing, run_benchmark returns a skipped result."""
    runner = BenchmarkRunner()
    result = runner.run_benchmark()
    assert result["status"] == "skipped"
    assert result["benchmark"] == "cinebench"
    assert "Cinebench.exe" in result["message"]



# ── abort/timeout taskkill paths ──────────────────────────────────────────────


def _make_first_event_preset_factory():
    """Returns a side_effect that yields a pre-set Event on the first call only.

    Patching ``threading.Event`` globally would break ``Thread.start()`` (which
    creates its own internal Events for ``_started``/``_stopped`` and crashes
    if those come back already set). We only want to override the FIRST Event
    created inside ``_run_cinebench`` -- the abort_event -- so subsequent
    Event() calls (Thread internals, watchdog, etc.) get real Events.
    """
    import threading
    real_event_cls = threading.Event
    preset = real_event_cls()
    preset.set()
    call_count = [0]

    def factory():
        call_count[0] += 1
        if call_count[0] == 1:
            return preset
        return real_event_cls()

    return factory


@patch("src.benchmarks.cinebench.prompt_approval", return_value=True)
@patch("src.benchmarks.cinebench.Path.read_text", return_value="")
@patch("src.benchmarks.cinebench.Path.write_text")
@patch("src.benchmarks.cinebench.Path.exists", return_value=True)
@patch("src.benchmarks.cinebench.subprocess.run")
@patch("src.benchmarks.cinebench.subprocess.Popen")
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_cinebench_user_abort_taskkills_cb_image_name(
    mock_isfile, mock_popen, mock_run, mock_exists, mock_write, mock_read, mock_approve,
):
    """User abort path must taskkill /IM Cinebench.exe -- it's detached from proc.pid via 'start /b'."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.pid = 4242
    mock_popen.return_value = mock_proc

    factory = _make_first_event_preset_factory()
    with patch("src.benchmarks.cinebench.threading.Event", side_effect=factory):
        runner = BenchmarkRunner(cinebench_path=r"C:\CB\Cinebench.exe")
        result = runner.run_benchmark(full_suite=False)

    assert result["status"] == "aborted"
    assert result["benchmark"] == "cinebench"

    # Both taskkills must fire on abort: /T to kill the cmd.exe tree, /IM to
    # kill Cinebench.exe (which 'start /b /wait' detached from proc's tree).
    taskkill_calls = [c.args[0] for c in mock_run.call_args_list]
    assert ["taskkill", "/F", "/T", "/PID", "4242"] in taskkill_calls
    assert ["taskkill", "/F", "/IM", "Cinebench.exe"] in taskkill_calls
    mock_proc.kill.assert_called_once()


@patch("src.benchmarks.cinebench._CINEBENCH_TIMEOUT", 0)
@patch("src.benchmarks.cinebench._keyboard_abort_watcher")
@patch("src.benchmarks.cinebench.prompt_approval", return_value=True)
@patch("src.benchmarks.cinebench.Path.read_text", return_value="")
@patch("src.benchmarks.cinebench.Path.write_text")
@patch("src.benchmarks.cinebench.Path.exists", return_value=True)
@patch("src.benchmarks.cinebench.subprocess.run")
@patch("src.benchmarks.cinebench.subprocess.Popen")
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_cinebench_timeout_taskkills_cb_image_name(
    mock_isfile, mock_popen, mock_run, mock_exists, mock_write, mock_read,
    mock_approve, mock_watcher,
):
    """Watchdog timeout path must also taskkill /IM Cinebench.exe, mirroring the abort path."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.pid = 7373
    mock_popen.return_value = mock_proc

    runner = BenchmarkRunner(cinebench_path=r"C:\CB\Cinebench.exe")
    result = runner.run_benchmark(full_suite=False)

    # Timeout raises subprocess.TimeoutExpired internally, caught and reported as error.
    assert result["status"] == "error"
    assert result["benchmark"] == "cinebench"
    assert result["message"] == "Timed out"

    taskkill_calls = [c.args[0] for c in mock_run.call_args_list]
    assert ["taskkill", "/F", "/T", "/PID", "7373"] in taskkill_calls
    assert ["taskkill", "/F", "/IM", "Cinebench.exe"] in taskkill_calls


def test_minimize_cinebench_window_returns_when_abort_set():
    """Pre-set abort_event short-circuits the polling loop without touching Win32 APIs.

    This pins the contract that the helper checks ``abort_event`` BEFORE its
    first EnumWindows call -- so the parent run loop can shut the helper down
    cleanly when the benchmark aborts/finishes.
    """
    import threading
    import time
    from src.benchmarks.cinebench import _minimize_cinebench_window

    abort_event = threading.Event()
    abort_event.set()

    start = time.monotonic()
    _minimize_cinebench_window("Cinebench.exe", 60.0, abort_event)
    elapsed = time.monotonic() - start

    # Should be near-instant; if the loop ran even once it would sleep 1 s.
    assert elapsed < 0.5, f"helper did not short-circuit on pre-set abort_event ({elapsed:.3f}s)"
