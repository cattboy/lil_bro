import pytest
from unittest.mock import patch, MagicMock

from src.benchmarks.cinebench import (
    BenchmarkRunner,
    find_cinebench,
    run_cpu_fallback,
    _stress_core,
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

def test_stress_core_runs():
    """Should run for at least 0.05s and return a positive iteration count."""
    result = _stress_core(0.05)
    assert isinstance(result, int)
    assert result > 0


def test_stress_core_duration_scales():
    """Longer duration → more iterations (roughly)."""
    short = _stress_core(0.05)
    long = _stress_core(0.15)
    assert long >= short


# ── run_cpu_fallback ──────────────────────────────────────────────────────────

@patch("src.benchmarks.cinebench.multiprocessing.Pool")
def test_cpu_fallback_success(mock_pool_cls):
    """Returns structured result with scores when multiprocessing works."""
    mock_pool = MagicMock()
    mock_pool.__enter__ = MagicMock(return_value=mock_pool)
    mock_pool.__exit__ = MagicMock(return_value=False)
    mock_pool.starmap.return_value = [100, 95, 105, 98]
    mock_pool_cls.return_value = mock_pool

    result = run_cpu_fallback(duration_secs=1)

    assert result["status"] == "success"
    assert result["benchmark"] == "cpu_stress"
    assert result["total_iterations"] == 398
    assert "CPU_Multi" in result["scores"]
    assert "CPU_Single" in result["scores"]


@patch("src.benchmarks.cinebench._stress_core", return_value=50)
@patch(
    "src.benchmarks.cinebench.multiprocessing.Pool",
    side_effect=RuntimeError("spawn failed"),
)
def test_cpu_fallback_multiprocessing_fails(mock_pool, mock_stress):
    """Falls back to single-core when multiprocessing can't start."""
    result = run_cpu_fallback(duration_secs=1)
    assert result["status"] == "success"
    assert result["cores_used"] == 1
    assert result["total_iterations"] == 50


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

@patch("src.benchmarks.cinebench.subprocess.Popen")
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_cinebench_success(mock_isfile, mock_popen):
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


@patch("src.benchmarks.cinebench.subprocess.Popen")
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_cinebench_full_suite(mock_isfile, mock_popen):
    """full_suite=True passes the AllTests flag."""
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (b"", b"")
    mock_proc.pid = 1234
    mock_popen.return_value = mock_proc

    runner = BenchmarkRunner(cinebench_path=r"C:\CB\Cinebench.exe")
    runner.run_benchmark(full_suite=True)
    call_args = mock_popen.call_args
    assert "g_CinebenchAllTests=true" in call_args[0][0]


@patch(
    "src.benchmarks.cinebench.subprocess.Popen",
    side_effect=Exception("crash"),
)
@patch("src.benchmarks.cinebench.os.path.isfile", return_value=True)
def test_run_cinebench_error(mock_isfile, mock_popen):
    """Cinebench crash → error result."""
    runner = BenchmarkRunner(cinebench_path=r"C:\CB\Cinebench.exe")
    result = runner.run_benchmark()
    assert result["status"] == "error"


# ── BenchmarkRunner.run_benchmark — fallback path ───────────────────────────

@patch("src.benchmarks.cinebench.run_cpu_fallback")
@patch("src.benchmarks.cinebench.prompt_approval", return_value=True)
@patch("src.benchmarks.cinebench.find_cinebench", return_value=None)
def test_run_fallback_when_no_cinebench(mock_find, mock_approve, mock_fallback):
    """Falls back to CPU stress test when Cinebench not found and user approves."""
    mock_fallback.return_value = {"status": "success", "benchmark": "cpu_stress"}
    runner = BenchmarkRunner()
    result = runner.run_benchmark()
    assert result["benchmark"] == "cpu_stress"
    mock_approve.assert_called_once()


@patch("src.benchmarks.cinebench.prompt_approval", return_value=False)
@patch("src.benchmarks.cinebench.find_cinebench", return_value=None)
def test_run_fallback_declined(mock_find, mock_approve):
    """User declines CPU fallback → skipped result."""
    runner = BenchmarkRunner()
    result = runner.run_benchmark()
    assert result["status"] == "skipped"


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
