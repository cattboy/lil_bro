"""
Benchmark orchestration — Cinebench 2024/2026.

Detects installed Cinebench across common paths, launches it via CLI, and
parses results.  When Cinebench is unavailable, both benchmark phases are
skipped and the user is shown installation instructions.
"""

import msvcrt
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from .thermal_monitor import ThermalWatchdog

from ..config import config as _cfg
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
    # Placed next to lil_bro.exe by the user
    str(Path.cwd() / "Cinebench.exe"),
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

_CINEBENCH_TIMEOUT = _cfg.benchmark.cinebench_timeout  # max seconds for a single run


def _keyboard_abort_watcher(abort_event: threading.Event) -> None:
    """
    Background thread — sets abort_event when Q, q, or Enter is pressed.

    Uses ``msvcrt.kbhit()`` (Windows, no Enter required for Q).  Polls every
    50 ms so it stays responsive without busy-spinning.
    """
    while not abort_event.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key in (b"q", b"Q", b"\r"):
                abort_event.set()
                return
        time.sleep(0.05)


def _benchmark_progress_printer(abort_event: threading.Event, start_time: float) -> None:
    """Prints elapsed time + abort hint every 30 s during a benchmark run."""
    while not abort_event.is_set():
        time.sleep(30)
        if abort_event.is_set():
            break
        elapsed = int(time.monotonic() - start_time)
        mins, secs = divmod(elapsed, 60)
        print_info(f"Still running... [{mins}m {secs:02d}s elapsed]  Press Q or Enter to abort.")


def find_cinebench() -> Optional[str]:
    """Search common install paths for Cinebench. Returns exe path or None."""
    for path in _CINEBENCH_SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    return None










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
        Run a Cinebench benchmark.

        Args:
            full_suite: If True, run all test modes; otherwise CPU single-core only.
            lhm_available: If True, enables the thermal watchdog during the run.
        Returns:
            dict with ``status``, ``benchmark``, ``scores``, and extra metadata.
        """
        if self.has_cinebench:
            return self._run_cinebench(full_suite, lhm_available)

        print_warning("Cinebench not found — benchmark phases will be skipped.")
        print_info("Cinebench is required to produce before/after scores.")
        print_info("  1. Download Cinebench from http://maxon.net/en/downloads/cinebench-downloads")
        print_info("  2. Place Cinebench.exe in the same folder as lil_bro.exe")
        print_info("  3. Re-run lil_bro")
        return {
            "status": "skipped",
            "benchmark": "cinebench",
            "message": "Cinebench not installed — place Cinebench.exe next to lil_bro.exe and re-run.",
        }

    # ── Cinebench ─────────────────────────────────────────────────────────

    def _run_cinebench(self, full_suite: bool, lhm_available: bool = False) -> dict:
        """Launch Cinebench via CLI and capture results."""
        mode = "All Tests" if full_suite else "CPU Single-Core"
        print_step(f"Running Cinebench ({mode})")
        print()  # newline so subsequent print_info calls appear on their own lines
        print_info(
            "This will take several minutes. NO TOUCHY /afk a bit while lil_bro runs the benchmark. "
            "Your PC will be under high load, set fans to WARP SPEED."
        )
        print_info("Press Q or Enter to abort the benchmark at any time.")

        # Build CLI args per docs/vendor-supplied/cinebench.md
        cb_flag = "g_CinebenchAllTests=true" if full_suite else "g_CinebenchCpu1Test=true"

        abort_event = threading.Event()

        # Keyboard watcher — active for the full duration of the run
        kb_thread = threading.Thread(
            target=_keyboard_abort_watcher, args=(abort_event,), daemon=True
        )
        kb_thread.start()

        # Progress printer — reminds the user how to abort every 30 s
        bench_start = time.monotonic()
        progress_thread = threading.Thread(
            target=_benchmark_progress_printer,
            args=(abort_event, bench_start),
            daemon=True,
        )
        progress_thread.start()

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
                            else "Aborted by user (Q or Enter)."
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
                abort_event.set()  # signal keyboard watcher and progress printer to exit cleanly
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
