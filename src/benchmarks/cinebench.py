"""
Benchmark orchestration -- Cinebench 2024/2026.

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
from ..utils.debug_logger import get_debug_logger
from ..utils.formatting import (
    print_step,
    print_step_done,
    print_error,
    print_info,
    print_warning,
    prompt_approval,
)
from ..utils.paths import get_lil_bro_dir, get_temp_dir

log = get_debug_logger()

# -- Cinebench discovery ------------------------------------------------------

from ..pipeline import _state

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

# Win32 ShowWindow nCmdShow codes used by _minimize_cinebench_window.
SW_HIDE = 0
SW_MINIMIZE = 6


from ..utils.formatting import notify_benchmark_started

def _keyboard_abort_watcher(abort_event: threading.Event) -> None:
    """
    Background thread -- sets abort_event when Q, q, or Enter is pressed.

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


def _minimize_cinebench_window(
    cb_exe: str,
    timeout: float,
    abort_event: threading.Event,
    cmd_parent_pid: int,
) -> None:
    """Minimize the Cinebench GUI once after launch, then leave the user alone.

    Identifies windows by their owning process executable name (e.g.
    ``Cinebench.exe``) rather than by window title. Cinebench 2026 spends
    the first ~100 s with title ``SplashScreen`` (no 'cinebench' substring),
    so title matching misses the splash and only catches the main window
    much later. Process matching catches both within seconds of launch.

    Also hides the helper ``cmd.exe`` process spawned by ``_run_cinebench``
    (identified by ``cmd_parent_pid``) as a belt-and-suspenders fallback in
    case ``STARTUPINFO``/``SW_HIDE`` ever fails to suppress its console
    window at spawn time. cmd windows are SW_HIDE'd (not minimized) so they
    disappear entirely rather than landing in the taskbar.

    Polls every second for up to ``timeout`` to tolerate slow systems. On
    the first match, hides/minimizes the windows and returns -- never
    touches focus again. The OS pops whatever was behind Cinebench
    (typically lil_bro) to the foreground naturally when its windows
    minimize.
    """
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # OpenProcess returns HANDLE (pointer). Without restype set, ctypes
    # defaults to c_int, and a high-bit-set handle would read as a negative
    # int that the `if not h` nullity check would mistake for a valid handle.
    kernel32.OpenProcess.restype = ctypes.c_void_p

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    cb_exe_lower = cb_exe.lower()
    own_pid = kernel32.GetCurrentProcessId()
    # Each entry: (hwnd, show_cmd). show_cmd is SW_MINIMIZE for Cinebench
    # windows and SW_HIDE for our spawned cmd window.
    found: list[tuple[int, int]] = []

    def _window_pid(hwnd) -> int:
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def _belongs_to_cinebench(hwnd):
        pid = _window_pid(hwnd)
        if pid == 0 or pid == own_pid:
            return False
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.c_ulong(260)
            if not kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return False
            return os.path.basename(buf.value).lower() == cb_exe_lower
        finally:
            kernel32.CloseHandle(h)

    def _belongs_to_our_cmd(hwnd) -> bool:
        # The outer cmd.exe spawned by subprocess.Popen has pid == cmd_parent_pid.
        # Match windows owned by exactly that pid, regardless of image name.
        pid = _window_pid(hwnd)
        return pid != 0 and pid == cmd_parent_pid

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

    def _callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        if _belongs_to_our_cmd(hwnd):
            found.append((hwnd, SW_HIDE))
        elif _belongs_to_cinebench(hwnd):
            found.append((hwnd, SW_MINIMIZE))
        return True

    callback = WNDENUMPROC(_callback)
    deadline = time.monotonic() + timeout
    while not abort_event.is_set() and time.monotonic() < deadline:
        found.clear()
        user32.EnumWindows(callback, 0)
        if found:
            for hwnd, show_cmd in found:
                user32.ShowWindow(hwnd, show_cmd)
            return  # one-shot -- never meddle with the user's session again
        time.sleep(1)


def find_cinebench() -> Optional[str]:
    """Search common install paths for Cinebench. Returns exe path or None."""
    for path in _CINEBENCH_SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    return None










# -- Benchmark runner ---------------------------------------------------------


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