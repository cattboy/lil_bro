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
@patch("src.benchmarks.cinebench.subprocess.Popen")
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_cinebench_success(mock_isfile, mock_popen, mock_approve):
    """Cinebench runs and returns success with parsed output."""
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (
        b"CB 2024 Score: CPU Multi 15320 pts\n",
        b"",
    )
    mock_proc.pid = 1234
    mock_popen.return_value = mock_proc

    runner = BenchmarkRunner(cinebench_path=r"C:\CB\Cinebench.exe")
    result = runner.run_benchmark(full_suite=False)

    assert result["status"] == "success"
    assert result["benchmark"] == "cinebench"
    # The CLI args list should include the single-core flag
    call_args = mock_popen.call_args
    assert "g_CinebenchCpu1Test=true" in call_args[0][0]


@patch("src.benchmarks.cinebench.prompt_approval", return_value=True)
@patch("src.benchmarks.cinebench.subprocess.Popen")
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_cinebench_full_suite(mock_isfile, mock_popen, mock_approve):
    """full_suite=True passes the AllTests flag."""
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.pid = 1234
    mock_popen.return_value = mock_proc

    runner = BenchmarkRunner(cinebench_path=r"C:\CB\Cinebench.exe")
    runner.run_benchmark(full_suite=True)
    call_args = mock_popen.call_args
    assert "g_CinebenchAllTests=true" in call_args[0][0]


@patch("src.benchmarks.cinebench.prompt_approval", return_value=True)
@patch(
    "src.benchmarks.cinebench.subprocess.Popen",
    side_effect=Exception("crash"),
)
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_cinebench_error(mock_isfile, mock_popen, mock_approve):
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
    output = "CB 2024 Score: CPU Multi 15320 pts\nGPU Score: 24310 pts\n"
    scores = BenchmarkRunner._parse_output(output)
    assert "CPU_Multi" in scores
    assert "GPU" in scores


def test_parse_output_single():
    output = "Single Core Score: 1823 pts\n"
    scores = BenchmarkRunner._parse_output(output)
    assert "CPU_Single" in scores


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
