"""
Benchmark orchestration -- Cinebench 2024/2026.

Detects installed Cinebench across common paths, launches it via CLI, and
parses results.  When Cinebench is unavailable, both benchmark phases are
skipped and the user is shown installation instructions.
"""

import os
import re
import subprocess
import threading
import time
from pathlib import Path  # re-exported for tests that @patch cinebench.Path
from typing import Optional

from ..config import config as _cfg
from ..pipeline import _state
from ..utils.debug_logger import get_debug_logger
from ..utils.formatting import (
    notify_benchmark_started,
    print_error,
    print_info,
    print_step,
    print_step_done,
    print_warning,
    prompt_approval,
)
from ..utils.paths import get_lil_bro_dir, get_temp_dir
from .cinebench_discovery import _REPO_ROOT, _CINEBENCH_SEARCH_PATHS, find_cinebench
from .cinebench_monitor import (
    SW_HIDE,
    SW_MINIMIZE,
    _benchmark_progress_printer,
    _keyboard_abort_watcher,
    _minimize_cinebench_window,
)
from .cinebench_parser import parse_output
from .thermal_monitor import ThermalWatchdog

log = get_debug_logger()

_CINEBENCH_TIMEOUT = _cfg.benchmark.cinebench_timeout  # max seconds for a single run


class BenchmarkRunner:
    """
    Orchestrates benchmark runs -- Cinebench if available, CPU fallback otherwise.

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
            print_warning("Cinebench not found -- benchmark phases will be skipped.")
            print_info("Cinebench is required to produce before/after scores.")
            print_info("  1. Download Cinebench from https://www.maxon.net/cinebench")
            print_info("  2. Place Cinebench.exe in the same folder as lil_bro.exe")
            print_info("  3. Re-run lil_bro")
            return {
                "status": "skipped",
                "benchmark": "cinebench",
                "message": "Cinebench not installed -- place Cinebench.exe next to lil_bro.exe and re-run.",
            }

        mode = "All Tests" if full_suite else "CPU Single-Core"
        if not prompt_approval(f"Run Cinebench ({mode})? This will take 10+ minutes, do NOT use the PC while it's running."):
            return {"status": "skipped", "benchmark": "cinebench", "message": "User declined benchmark."}

        notify_benchmark_started()
        return self._run_cinebench(full_suite, lhm_available)

    # -- Cinebench ------------------------------------------------------------

    def _run_cinebench(self, full_suite: bool, lhm_available: bool = False) -> dict:
        """Launch Cinebench via CLI and capture results."""
        # Path containing a double-quote would escape the batch-file quoting
        # below ("...""{self.cinebench_path}"...") and let arbitrary cmd.exe
        # tokens through. find_cinebench() only returns paths from a hardcoded
        # search list -- none of which contain " -- but a future caller passing
        # an arbitrary path needs this guard.
        if '"' in str(self.cinebench_path):
            reason = (
                f"Cinebench path contains an unsupported character ('\"'): "
                f"{self.cinebench_path}"
            )
            print_error(reason)
            log.error("Cinebench: %s", reason)
            return {"status": "error", "benchmark": "cinebench", "message": reason}

        mode = "All Tests" if full_suite else "CPU Single-Core"
        print_step(f"Running Cinebench ({mode})")
        print()  # newline so subsequent print_info calls appear on their own lines
        print_info(
            "This will take several minutes. NO TOUCHY /afk a bit while lil_bro runs the benchmark. "
            "Your PC will be under high load, set fans to WARP SPEED."
        )
        print_info("Press Esc, Q or Enter to abort the benchmark at any time.")

        # Build CLI args per docs/vendor-supplied/cinebench.md
        cb_flag = "g_CinebenchAllTests=true" if full_suite else "g_CinebenchCpu1Test=true"
        cb_exe = os.path.basename(self.cinebench_path)  # for image-name kill on abort/timeout

        # Output file -- receives the full Cinebench console log
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

        # Keyboard watcher -- active for the full duration of the run
        kb_thread = threading.Thread(
            target=_keyboard_abort_watcher, args=(abort_event,), daemon=True
        )
        kb_thread.start()

        # Progress printer -- reminds the user how to abort every 30 s
        bench_start = time.monotonic()
        progress_thread = threading.Thread(
            target=_benchmark_progress_printer,
            args=(abort_event, bench_start),
            daemon=True,
        )
        progress_thread.start()

        # Thermal watchdog -- only when LHM sensor data is available
        watchdog: Optional[ThermalWatchdog] = None
        if lhm_available:
            watchdog = ThermalWatchdog(abort_event)
            watchdog.start()

        # Hide the outer cmd.exe console window in GUI mode. STARTUPINFO+SW_HIDE
        # keeps a real console alive for Cinebench's vendor-required
        # 'start /b /wait "parentconsole"' redirect; CREATE_NO_WINDOW would strip
        # the console entirely and risk silent output loss.
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = SW_HIDE

        try:
            proc = subprocess.Popen(
                ["cmd.exe", "/C", str(batch_file)],
                startupinfo=si,
            )

            # One-shot minimize of the Cinebench GUI on launch. 60 s grace window
            # so slow systems still have time to finish launching it. Matched by
            # process executable, not title -- the splash screen has no 'cinebench'
            # in its title for the first ~100 s of the run. Also hides the cmd.exe
            # window spawned above as a belt-and-suspenders fallback if STARTUPINFO
            # ever fails to suppress it.
            threading.Thread(
                target=_minimize_cinebench_window,
                args=(cb_exe, 60.0, abort_event, proc.pid),
                daemon=True,
            ).start()

            start = time.monotonic()
            try:
                while proc.poll() is None:
                    if abort_event.is_set() or _state.is_cancelled():
                        gui_cancelled = _state.is_cancelled() and not abort_event.is_set()
                        proc.kill()
                        # /T kills the batch cmd.exe tree; /IM kills Cinebench itself
                        # which is detached from proc's tree by 'start /b /wait'.
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            capture_output=True,
                        )
                        subprocess.run(
                            ["taskkill", "/F", "/IM", cb_exe],
                            capture_output=True,
                        )
                        proc.communicate()
                        if watchdog and watchdog.abort_reason:
                            reason = watchdog.abort_reason
                        elif gui_cancelled:
                            reason = "Cancelled from GUI."
                        else:
                            reason = "Aborted by user (Q or Enter)."
                        print_step_done(False)
                        print_warning(f"Benchmark aborted: {reason}")
                        log.warning("Cinebench: Benchmark aborted -- %s", reason)
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
                        subprocess.run(
                            ["taskkill", "/F", "/IM", cb_exe],
                            capture_output=True,
                        )
                        proc.communicate()
                        raise subprocess.TimeoutExpired(
                            str(self.cinebench_path), _CINEBENCH_TIMEOUT
                        )
                    time.sleep(0.5)

                proc.communicate()  # drain (no pipes, but ensures clean exit)

            finally:
                abort_event.set()  # signal all background threads to exit cleanly
                if watchdog:
                    watchdog.stop()

            # Guard 1: honour a cancel that fired concurrently with process exit
            if _state.is_cancelled():
                reason = "Cancelled from GUI."
                print_step_done(False)
                print_warning(f"Benchmark aborted: {reason}")
                log.warning("Cinebench: Benchmark aborted -- %s (concurrent with process exit)", reason)
                return {
                    "status": "aborted",
                    "benchmark": "cinebench",
                    "message": reason,
                }

            raw = output_file.read_text(encoding="utf-8", errors="replace") if output_file.exists() else ""
            scores = self._parse_output(raw, full_suite)

            # Guard 2: no cancel signal but no scores -- tool failure (EULA screen, AV quarantine, driver crash)
            if not scores:
                reason = "Cinebench exited without producing scores -- benchmark may have been interrupted."
                print_step_done(False)
                print_warning(reason)
                log.warning("Cinebench: Process exited but no scores parsed; treating as error (no cancel signal).")
                return {
                    "status": "error",
                    "benchmark": "cinebench",
                    "raw_output": raw[:500],
                    "scores": {},
                    "message": reason,
                }

            print_step_done(True)

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
            print_error("Cinebench timed out, timeout can be increased in lil_bro_config.json -> cinebench_timeout")
            log.warning(
                "Cinebench: Benchmark timed out -- Cinebench did not complete within timeperiod, "
                "update lil_bro_config.json -> cinebench_timeout"
            )
            return {"status": "error", "benchmark": "cinebench", "message": "Timed out"}

        except Exception as e:
            print_step_done(False)
            print_error(f"Cinebench failed: {e}")
            log.error("Cinebench: Benchmark failed -- %s", e)
            return {"status": "error", "benchmark": "cinebench", "message": str(e)}

    @staticmethod
    def _parse_output(output: str, full_suite: bool = False) -> dict[str, str]:
        """Extract scores from Cinebench console log. Delegates to cinebench_parser."""
        return parse_output(output, full_suite)