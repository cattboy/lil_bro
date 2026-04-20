"""
Benchmark orchestration — Cinebench 2024/2026.

Detects installed Cinebench across common paths, launches it via CLI, and
parses results.  When Cinebench is unavailable, both benchmark phases are
skipped and the user is shown installation instructions.
"""

import msvcrt
import os
import re
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
from ..utils.paths import get_lil_bro_dir, get_temp_dir

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


def _refocus_console_window(delay: float, abort_event: threading.Event) -> None:
    """Bring the lil_bro console back to the foreground after Cinebench loads."""
    import ctypes
    time.sleep(delay)
    if abort_event.is_set():
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if not hwnd:
            return
        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


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
        if not self.has_cinebench:
            print_warning("Cinebench not found — benchmark phases will be skipped.")
            print_info("Cinebench is required to produce before/after scores.")
            print_info("  1. Download Cinebench from https://www.maxon.net/cinebench")
            print_info("  2. Place Cinebench.exe in the same folder as lil_bro.exe")
            print_info("  3. Re-run lil_bro")
            return {
                "status": "skipped",
                "benchmark": "cinebench",
                "message": "Cinebench not installed — place Cinebench.exe next to lil_bro.exe and re-run.",
            }

        mode = "All Tests" if full_suite else "CPU Single-Core"
        if not prompt_approval(f"Run Cinebench ({mode})?"):
            return {"status": "skipped", "benchmark": "cinebench", "message": "User declined benchmark."}

        return self._run_cinebench(full_suite, lhm_available)

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

        # Output file — receives the full Cinebench console log
        output_file = get_temp_dir() / "cinebench_output.txt"

        # Batch file wraps the invocation so we get the Windows console log.
        # 'start /b /wait "parentconsole"' is required per vendor docs to enable output.
        # The ""path" flag > "file"" quoting handles paths with spaces inside cmd /C.
        batch_file = get_temp_dir() / "_run_cinebench.bat"
        batch_file.write_text(
            "@echo off\r\n"
            f'start /b /wait "parentconsole" cmd.exe /C ""{self.cinebench_path}" {cb_flag} > "{output_file}""\r\n',
            encoding="ascii",
        )

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
            proc = subprocess.Popen(["cmd.exe", "/C", str(batch_file)])

            # Refocus lil_bro after Cinebench has had time to open its GUI
            threading.Thread(
                target=_refocus_console_window, args=(30.0, abort_event), daemon=True
            ).start()

            start = time.monotonic()
            try:
                while proc.poll() is None:
                    if abort_event.is_set():
                        proc.kill()
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            capture_output=True,
                        )
                        proc.communicate()
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

                proc.communicate()  # drain (no pipes, but ensures clean exit)

            finally:
                abort_event.set()  # signal keyboard watcher and progress printer to exit cleanly
                if watchdog:
                    watchdog.stop()

            print_step_done(True)

            raw = output_file.read_text(encoding="utf-8", errors="replace") if output_file.exists() else ""
            scores = self._parse_output(raw, full_suite)

            # Write filtered results file (FINDSTR "CB" equivalent) for human reference
            cb_lines = [ln for ln in raw.splitlines() if re.match(r"^\s*CB\s+", ln)]
            results_file = get_lil_bro_dir() / "cinebench_results.txt"
            results_file.write_text(
                "\n".join(cb_lines) + "\n" if cb_lines else "No CB scores found.\n",
                encoding="utf-8",
            )

            return {
                "status": "success",
                "benchmark": "cinebench",
                "raw_output": raw[:500],
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
    def _parse_output(output: str, full_suite: bool = False) -> dict[str, str]:
        """Extract scores from Cinebench console log.

        Score line format: CB 247.39 (0.00)
        Context lines (e.g. 'Running Single CPU Render Test...') label each score.
        """
        scores: dict[str, str] = {}
        last_context = ""

        for line in output.splitlines():
            stripped = line.strip()
            low = stripped.lower()

            if low.startswith("running") or "render test" in low:
                last_context = low

            m = re.match(r"^CB\s+([\d.]+)\s+\([\d.]+\)", stripped)
            if not m:
                continue

            pts = f"{m.group(1)} pts"

            if "single" in last_context or "cpu1" in last_context:
                scores["CPU_Single"] = pts
            elif "multi" in last_context or "cpux" in last_context or "nthread" in last_context:
                scores["CPU_Multi"] = pts
            elif "gpu" in last_context:
                scores["GPU"] = pts
            else:
                if "CPU_Single" not in scores:
                    scores["CPU_Single"] = pts
                elif "CPU_Multi" not in scores:
                    scores["CPU_Multi"] = pts
                else:
                    scores[f"Score_{len(scores) + 1}"] = pts

        return scores
