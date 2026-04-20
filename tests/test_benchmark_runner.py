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
