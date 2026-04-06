"""
Benchmark orchestration — Cinebench 2024/2026 with CPU stress fallback.

Detects installed Cinebench across common paths, launches it via CLI, and
parses results.  When Cinebench is unavailable, falls back to a pure-Python
multiprocessing CPU stress test that generates enough thermal load for
monitoring while producing a relative before/after score.
"""

import math
import msvcrt
import multiprocessing
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from .thermal_monitor import ThermalWatchdog

from ..utils.action_logger import action_logger
from ..utils.formatting import (
    print_step,
    print_step_done,
    print_error,
    print_info,
    print_warning,
    prompt_approval,
)

# ── Cinebench discovery ──────────────────────────────────────────────────────

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)

_CINEBENCH_SEARCH_PATHS = [
    # Bundled with lil_bro (future installer puts it here)
    os.path.join(_REPO_ROOT, "bench-exe", "Cinebench.exe"),
    # Maxon default installs
    r"C:\Program Files\Maxon Cinebench 2024\Cinebench.exe",
    r"C:\Program Files\Maxon Cinebench\Cinebench.exe",
    r"C:\Program Files\Maxon Cinema 4D 2026\Cinebench.exe",
    r"C:\Program Files\Maxon Cinema 4D 2024\Cinebench.exe",
    # Desktop shortcuts
    r"C:\Users\Public\Desktop\Cinebench.exe",
    os.path.expanduser(r"~\Desktop\Cinebench.exe"),
    # Steam
    os.path.expandvars(
        r"%ProgramFiles(x86)%\Steam\steamapps\common\Cinebench 2024\Cinebench.exe"
    ),
    os.path.expandvars(
        r"%ProgramFiles(x86)%\Steam\steamapps\common\Cinebench\Cinebench.exe"
    ),
    # User local apps
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Cinebench 2024\Cinebench.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Cinebench\Cinebench.exe"),
]

_CINEBENCH_TIMEOUT = 600  # 10 minutes max for a single run


def _keyboard_abort_watcher(abort_event: threading.Event) -> None:
    """
    Background thread — sets abort_event when Q or q is pressed.

    Uses ``msvcrt.kbhit()`` (Windows, no Enter required).  Polls every 50 ms
    so it stays responsive without busy-spinning.
    """
    while not abort_event.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key in (b"q", b"Q"):
                abort_event.set()
                return
        time.sleep(0.05)


def find_cinebench() -> Optional[str]:
    """Search common install paths for Cinebench. Returns exe path or None."""
    for path in _CINEBENCH_SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    return None


# ── CPU fallback benchmark ───────────────────────────────────────────────────

_FALLBACK_DURATION = 30  # seconds — enough to observe thermal trends


def _stress_core(duration_secs: float) -> int:
    """
    Stress a single CPU core with trigonometric math until time runs out.

    Returns the number of completed 1 000-op iterations. This function lives
    at module level so ``multiprocessing`` can pickle it on Windows.
    """
    iterations = 0
    deadline = time.monotonic() + duration_secs
    while time.monotonic() < deadline:
        x = 0.0
        for i in range(1000):
            x = math.sin(x + i) + math.cos(x * 0.999)
        iterations += 1
    return iterations


def run_cpu_fallback(duration_secs: int = _FALLBACK_DURATION) -> dict:
    """
    Lightweight CPU stress test using all available cores.

    Runs parallel trig math for *duration_secs* and returns a relative score
    (total iterations across all cores).  Not comparable to Cinebench points,
    but good for before/after deltas and generating thermal load.
    """
    core_count = os.cpu_count() or 4
    print_info(
        f"Running CPU stress test — {core_count} cores x {duration_secs}s"
    )
    print_info(
        "Your PC will be under full CPU load. Avoid heavy tasks during the test."
    )

    start = time.monotonic()
    try:
        with multiprocessing.Pool(processes=core_count) as pool:
            results = pool.starmap(
                _stress_core, [(float(duration_secs),)] * core_count
            )
    except Exception as e:
        # Fallback to single-core if multiprocessing setup fails
        print_warning(f"Multiprocessing unavailable ({e}) — running single-core.")
        results = [_stress_core(float(duration_secs))]
        core_count = 1

    elapsed = time.monotonic() - start
    total = sum(results)
    per_core = total / core_count

    return {
        "status": "success",
        "benchmark": "cpu_stress",
        "cores_used": core_count,
        "duration_seconds": round(elapsed, 1),
        "total_iterations": total,
        "scores": {
            "CPU_Multi": f"{total:,} iterations ({core_count} cores)",
            "CPU_Single": f"{per_core:,.0f} iterations/core",
        },
    }


# ── Benchmark runner ─────────────────────────────────────────────────────────


class BenchmarkRunner:
    """
    Orchestrates benchmark runs — Cinebench if available, CPU fallback otherwise.

    Usage::

        runner = BenchmarkRunner()
        result = runner.run_benchmark()
        print(result["scores"])
    """

    def __init__(self, cinebench_path: Optional[str] = None):
        if cinebench_path and os.path.isfile(cinebench_path):
            self.cinebench_path = cinebench_path
        else:
            self.cinebench_path = find_cinebench()
        self.has_cinebench = self.cinebench_path is not None

    def run_benchmark(self, full_suite: bool = False, lhm_available: bool = False) -> dict:
        """
        Run a benchmark — Cinebench if installed, CPU stress fallback otherwise.

        Args:
            full_suite: If True and Cinebench is available, run all test modes.
                        If False, run CPU single-core only.
            lhm_available: If True, enables the thermal watchdog during the run.
        Returns:
            dict with ``status``, ``benchmark``, ``scores``, and extra metadata.
        """
        if self.has_cinebench:
            return self._run_cinebench(full_suite, lhm_available)

        print_warning("Cinebench not found — falling back to built-in CPU stress test.")
        if not prompt_approval("Run built-in CPU stress test instead?"):
            return {"status": "skipped", "message": "User declined fallback benchmark"}
        return run_cpu_fallback()

    # ── Cinebench ─────────────────────────────────────────────────────────

    def _run_cinebench(self, full_suite: bool, lhm_available: bool = False) -> dict:
        """Launch Cinebench via CLI and capture results."""
        mode = "All Tests" if full_suite else "CPU Single-Core"
        print_step(f"Running Cinebench ({mode})")
        print_info(
            "This will take several minutes. "
            "Your PC will be under high load — avoid heavy tasks."
        )
        print_info("Press Q to abort the benchmark at any time.")

        # Build CLI args per docs/vendor-supplied/cinebench.md
        cb_flag = "g_CinebenchAllTests=true" if full_suite else "g_CinebenchCpu1Test=true"

        abort_event = threading.Event()

        # Keyboard watcher — active for the full duration of the run
        kb_thread = threading.Thread(
            target=_keyboard_abort_watcher, args=(abort_event,), daemon=True
        )
        kb_thread.start()

        # Thermal watchdog — only when LHM sensor data is available
        watchdog: Optional[ThermalWatchdog] = None
        if lhm_available:
            watchdog = ThermalWatchdog(abort_event)
            watchdog.start()

        try:
            proc = subprocess.Popen(
                [str(self.cinebench_path), cb_flag],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            start = time.monotonic()
            try:
                while proc.poll() is None:
                    if abort_event.is_set():
                        proc.kill()
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            capture_output=True,
                        )
                        proc.communicate()  # drain pipes
                        reason = (
                            watchdog.abort_reason
                            if watchdog and watchdog.abort_reason
                            else "Aborted by user (Q key)."
                        )
                        print_step_done(False)
                        print_warning(f"Benchmark aborted: {reason}")
                        action_logger.log_action(
                            "Cinebench",
                            "Benchmark aborted",
                            details=reason,
                            outcome="FAIL",
                        )
                        return {
                            "status": "aborted",
                            "benchmark": "cinebench",
                            "message": reason,
                        }
                    if time.monotonic() - start >= _CINEBENCH_TIMEOUT:
                        proc.kill()
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            capture_output=True,
                        )
                        proc.communicate()
                        raise subprocess.TimeoutExpired(
                            str(self.cinebench_path), _CINEBENCH_TIMEOUT
                        )
                    time.sleep(0.5)

                stdout, stderr = proc.communicate()  # normal completion

            finally:
                abort_event.set()  # signal keyboard watcher to exit cleanly
                if watchdog:
                    watchdog.stop()

            print_step_done(True)

            out = (stdout.decode("utf-8", errors="replace") + "\n" +
                   stderr.decode("utf-8", errors="replace"))
            scores = self._parse_output(out)

            return {
                "status": "success",
                "benchmark": "cinebench",
                "raw_output": out[:500],
                "scores": scores,
            }

        except subprocess.TimeoutExpired:
            print_step_done(False)
            print_error("Cinebench timed out after 10 minutes.")
            action_logger.log_action(
                "Cinebench",
                "Benchmark timed out",
                details="Cinebench did not complete within 10 minutes.",
                outcome="FAIL",
            )
            return {"status": "error", "benchmark": "cinebench", "message": "Timed out"}

        except Exception as e:
            print_step_done(False)
            print_error(f"Cinebench failed: {e}")
            action_logger.log_action(
                "Cinebench",
                "Benchmark failed",
                details=str(e),
                outcome="FAIL",
            )
            return {"status": "error", "benchmark": "cinebench", "message": str(e)}

    @staticmethod
    def _parse_output(output: str) -> dict[str, str]:
        """Extract score lines from Cinebench console output."""
        scores: dict[str, str] = {}
        for line in output.splitlines():
            low = line.lower()
            if "pts" not in low and "score" not in low:
                continue
            if "single" in low:
                scores["CPU_Single"] = line.strip()
            elif "multi" in low or "cpu" in low:
                scores["CPU_Multi"] = line.strip()
            elif "gpu" in low:
                scores["GPU"] = line.strip()
        return scores
