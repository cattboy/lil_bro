"""
LibreHardwareMonitor sidecar process manager.

Launches LHM as a background process with its HTTP server on port 8085,
waits for readiness, and tears down on exit. Gracefully degrades if LHM
is unavailable or the port is occupied.

PawnIO build prerequisite: lhm-server.exe embeds PawnIO.sys only when
tools/PawnIO/dist/ exists at build time. That directory requires WDK +
CMake + test-signing -- it is never built in CI. Without PawnIO, lhm-server
falls back to WMI-only sensors (no ring-0 access). This is expected; do not
attempt to fix the WDK build chain here.
"""

import ctypes
import json
import os
import subprocess
import threading
import time
import urllib.request
from typing import Optional

from ...utils.action_logger import action_logger
from ...utils.debug_logger import get_debug_logger
from ...utils.formatting import print_dim, print_info, print_step, print_step_done, print_warning
from ...utils.platform import is_admin
from ...utils.subprocess_utils import CREATE_NO_WINDOW
from .lhm_discovery import _LHM_SEARCH_PATHS, _PROJECT_ROOT, find_lhm_executable
from .lhm_http import (
    LHM_PORT, LHM_URL, _MAX_RESPONSE_BYTES, _POLL_INTERVAL, _STARTUP_TIMEOUT,
    _is_lhm_responding,
)
from .lhm_process_utils import _find_elevated_pid, _is_port_in_use

log = get_debug_logger()


class LHMSidecar:
    """
    Manages the LibreHardwareMonitor process lifecycle.

    Usage:
        sidecar = LHMSidecar()
        if sidecar.start():
            # LHM is running and responding on port 8085
            ...
        sidecar.stop()
    """

    def __init__(self, executable_path: Optional[str] = None):
        self._process: Optional[subprocess.Popen] = None
        self._exe_path = executable_path
        self._already_running = False
        self._elevated = False  # True when launched via ShellExecuteW runas
        self._stdout_lines: list[str] = []
        self._stderr_lines: list[str] = []
        # Failure attribution -- read by thermal_guidance.describe_sidecar_failure.
        # last_failure_kind labels WHICH start() branch failed; returncode/stderr
        # are captured only for the exited-immediately branch (the one that has
        # them). Reset at the top of every start() attempt (last-attempt-wins).
        self.last_failure_kind: Optional[str] = None
        self.last_returncode: Optional[int] = None
        self.last_stderr_lines: list[str] = []

    @property
    def is_running(self) -> bool:
        """True if LHM is responding on its HTTP endpoint."""
        return _is_lhm_responding()

    def start(self) -> bool:
        """
        Launch LHM sidecar. Returns True if LHM is ready on port 8085.

        Handles three scenarios:
        1. LHM already running -> attach (don't launch a second instance)
        2. Port occupied by something else -> warn and skip
        3. LHM not running -> launch subprocess and wait for readiness

        On failure, records ``last_failure_kind`` (+ returncode/stderr for the
        exited-immediately branch) so thermal_guidance.describe_sidecar_failure
        can attribute the cause. State resets at the top of every attempt --
        last-attempt-wins, NOT record-once: a retry that hits a different cause
        (user freed the port but antivirus now blocks the exe) must show the NEW
        cause, and a retry that succeeds must clear the stale one. NOTE: a
        successful start() that yields no CPU sensors (PawnIO/Secure-Boot blocked)
        returns True with no failure kind -- that "no_sensors" case is detected by
        the launch site, not here, because start() genuinely succeeded.
        """
        # Fresh slate for this attempt's failure attribution.
        self.last_failure_kind = None
        self.last_returncode = None
        self.last_stderr_lines = []

        # Scenario 1 & 2: check if port is already in use
        if _is_port_in_use(LHM_PORT):
            if _is_lhm_responding():
                print_info(
                    "LibreHardwareMonitor already running -- attaching to existing instance."
                )
                self._already_running = True
                return True
            else:
                self.last_failure_kind = "port_in_use"
                print_warning(
                    f"Port {LHM_PORT} is in use by another application -- "
                    "thermal monitoring unavailable."
                )
                return False

        # Scenario 3: find and launch a thermal sensor server
        if self._exe_path:
            exe = self._exe_path
            is_custom = os.path.basename(exe) == "lhm-server.exe"
        else:
            exe, is_custom = find_lhm_executable()

        if not exe:
            self.last_failure_kind = "not_found"
            print_warning(
                "Thermal sensor server not found. Thermal monitoring unavailable.\n"
                "  (lhm-server.exe was not bundled, and LibreHardwareMonitor is not installed)"
            )
            return False

        server_label = "lhm-server" if is_custom else "LibreHardwareMonitor"
        print_step(f"Launching {server_label} sidecar")

        # lhm-server.exe has port hardcoded to 8085 -- no CLI flag needed.
        # Full LHM requires --http-port to enable its built-in web server.
        # Pass --parent-pid so lhm-server.exe self-exits when lil_bro terminates
        # (works both for direct subprocess and ShellExecuteW-elevated launches).
        parent_flag = ["--parent-pid", str(os.getpid())] if is_custom else []
        cmd = [exe] if is_custom else [exe, "--http-port", str(LHM_PORT)]

        try:
            if is_admin():
                # Running as admin -- subprocess inherits the token directly.
                self._process = subprocess.Popen(
                    cmd + parent_flag,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=CREATE_NO_WINDOW,
                )
                threading.Thread(target=self._drain_stdout, daemon=True).start()
                threading.Thread(target=self._drain_stderr, daemon=True).start()
            else:
                # Not admin -- lhm-server.exe needs admin to install PawnIO on
                # first run.  Elevate via ShellExecuteW so the UAC prompt appears
                # on behalf of lhm-server.exe specifically.
                extra_args = " ".join(parent_flag)
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None,        # hwnd
                    "runas",     # verb -- triggers UAC elevation
                    exe,
                    extra_args or None,
                    None,        # working directory
                    0,           # SW_HIDE
                )
                if ret <= 32:
                    self.last_failure_kind = "elevation_failed"
                    print_step_done(False)
                    print_warning(
                        "Could not elevate lhm-server.exe (ShellExecuteW returned "
                        f"{ret}). Thermal monitoring unavailable."
                    )
                    return False
                self._elevated = True
        except Exception as e:
            self.last_failure_kind = "launch_error"
            print_step_done(False)
            print_warning(f"Failed to launch {server_label}: {e}")
            return False

        # Wait for HTTP readiness
        _pawnio_step_shown = False
        deadline = time.monotonic() + _STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if _is_lhm_responding():
                print_step_done(True)
                pid_str = str(self._process.pid) if self._process else "elevated"
                log.info("LHM Sidecar: Launched (PID %s) Port %s", pid_str, LHM_PORT)
                time.sleep(0.3)  # brief flush window for drain threads
                # Log PawnIO install outcome from lhm-server stdout
                for line in self._stdout_lines:
                    if "pawnio installed and running" in line.lower():
                        action_logger.log_action(
                            "PawnIO", "Driver installed via Driver Store", outcome="PASS"
                        )
                        break
                    if "pawnio installed but service did not start" in line.lower():
                        action_logger.log_action(
                            "PawnIO", "Driver installed but service failed", outcome="FAIL"
                        )
                        break
                # Surface any PawnIO warnings from stderr
                for line in self._stderr_lines:
                    if "pawnio" in line.lower():
                        print_warning(f"[lhm-server] {line}")
                        log.debug("LHM Sidecar: PawnIO activity -- %s", line.strip())
                return True

            # Surface PawnIO install progress so the user sees activity during
            # the Driver Store install (can take 10-30s with no other output).
            if not _pawnio_step_shown:
                for line in self._stdout_lines + self._stderr_lines:
                    if "installing pawnio" in line.lower():
                        print()  # end the open "Launching sidecar" step line
                        print_step("Installing PawnIO kernel driver")
                        action_logger.log_action("PawnIO", "Driver Store installation started")
                        _pawnio_step_shown = True
                        break

            # Early exit if subprocess already died
            if self._process is not None and self._process.poll() is not None:
                rc = self._process.returncode
                self.last_failure_kind = "exited_immediately"
                self.last_returncode = rc
                self.last_stderr_lines = list(self._stderr_lines)
                print_step_done(False)
                print_warning(
                    f"lhm-server.exe exited immediately (exit code {rc}). "
                    "Thermal monitoring unavailable."
                )
                if self._stderr_lines:
                    for line in self._stderr_lines[-10:]:
                        print_dim(f"  [lhm-server] {line}")
                self._process = None
                return False
            time.sleep(_POLL_INTERVAL)

        # Timeout -- process alive but HTTP never became ready
        self.last_failure_kind = "timeout"
        self.last_stderr_lines = list(self._stderr_lines)
        print_step_done(False)
        print_warning(
            f"LibreHardwareMonitor launched but /data.json not reachable after "
            f"{_STARTUP_TIMEOUT}s. Thermal monitoring unavailable."
        )
        if self._stderr_lines:
            for line in self._stderr_lines[-10:]:
                print_dim(f"  [lhm-server] {line}")
        self._kill_process()
        return False

    def _drain_stderr(self) -> None:
        """Read stderr from subprocess into _stderr_lines (daemon thread)."""
        proc = self._process
        if proc is None or proc.stderr is None:
            return
        try:
            for raw_line in proc.stderr:
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                if line:
                    self._stderr_lines.append(line)
        except (ValueError, OSError):
            pass  # pipe closed on normal shutdown

    def _drain_stdout(self) -> None:
        """Read stdout from subprocess into _stdout_lines (daemon thread)."""
        proc = self._process
        if proc is None or proc.stdout is None:
            return
        try:
            for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                if line:
                    self._stdout_lines.append(line)
        except (ValueError, OSError):
            pass

    def stop(self) -> None:
        """Tear down the LHM sidecar if we launched it."""
        if self._already_running:
            # We didn't start it -- don't kill it
            return
        if self._request_graceful_shutdown():
            log.info("LHM Sidecar: Stopped (graceful)")
            self._elevated = False
            self._process = None
            return
        self._kill_process()

    def _request_graceful_shutdown(self) -> bool:
        """Ask lhm-server to drain via /shutdown and wait for the process to exit.

        Cleanup must block on this so the OS releases the PawnIO driver handle
        (via Computer.Close() in lhm-server's CTS-cancellation path) before
        _uninstall_pawnio() runs.  Otherwise the SCM cannot remove the service
        entry without a reboot.

        Waits are capped at 5 s: a healthy lhm-server exits well under 2 s
        after /shutdown; past 5 s it is hung and _kill_process() takes over
        (process death releases the driver handle regardless).
        """
        try:
            req = urllib.request.Request(
                f"http://localhost:{LHM_PORT}/shutdown", method="POST"
            )
            urllib.request.urlopen(req, timeout=2).close()
        except Exception:
            return False

        if self._process is not None:
            try:
                self._process.wait(timeout=5)
            except Exception:
                return False
            return True

        if self._elevated:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if _find_elevated_pid("lhm-server.exe") is None:
                    return True
                time.sleep(0.25)
            return False

        return True

    def _kill_process(self) -> None:
        if self._elevated:
            # lhm-server.exe was launched elevated via ShellExecuteW -- we have
            # no Popen handle.  It self-exits via --parent-pid monitoring when
            # lil_bro terminates.  Best-effort kill via tasklist PID lookup.
            pid = _find_elevated_pid("lhm-server.exe")
            if pid:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        timeout=5,
                        creationflags=CREATE_NO_WINDOW,
                    )
                except Exception:
                    pass  # safe: subprocess cleanup is best-effort
                # taskkill /F is fire-and-forget -- wait for the process to
                # actually disappear so the PawnIO driver handle is released
                # before downstream cleanup attempts to delete the service.
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline:
                    if _find_elevated_pid("lhm-server.exe") is None:
                        break
                    time.sleep(0.25)
            log.info("LHM Sidecar: Stopped (elevated)")
            self._elevated = False
            return

        if self._process is None:
            return
        pid = self._process.pid
        try:
            self._process.terminate()
            self._process.wait(timeout=3)
        except Exception:
            # terminate() timed out or was denied -- try kill() then taskkill.
            # On Windows, terminate() and kill() both call TerminateProcess(); if
            # that fails (e.g. access-denied on an elevated process), fall back to
            # `taskkill /F /T` which goes through a separate OS code path and also
            # kills the full process tree.
            try:
                self._process.kill()
            except Exception:
                pass  # safe: process may already be dead
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=5,
                    creationflags=CREATE_NO_WINDOW,
                )
            except Exception:
                pass  # safe: taskkill fallback is best-effort
        finally:
            log.info("LHM Sidecar: Stopped")
            self._process = None

    def fetch_data(self) -> Optional[dict]:
        """Fetch the current sensor tree from LHM. Returns None on failure."""
        try:
            req = urllib.request.Request(LHM_URL)
            with urllib.request.urlopen(req, timeout=2) as resp:
                return json.loads(resp.read(_MAX_RESPONSE_BYTES))
        except Exception:
            return None