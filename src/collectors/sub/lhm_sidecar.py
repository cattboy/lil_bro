"""
LibreHardwareMonitor sidecar process manager.

Launches LHM as a background process with its HTTP server on port 8085,
waits for readiness, and tears down on exit. Gracefully degrades if LHM
is unavailable or the port is occupied.

PawnIO build prerequisite: lhm-server.exe embeds PawnIO.sys only when
tools/PawnIO/dist/ exists at build time. That directory requires WDK +
CMake + test-signing — it is never built in CI. Without PawnIO, lhm-server
falls back to WMI-only sensors (no ring-0 access). This is expected; do not
attempt to fix the WDK build chain here.
"""

import ctypes
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from typing import Optional

from ...utils.formatting import print_step, print_step_done, print_warning, print_info, print_dim
from ...utils.action_logger import action_logger
from ...utils.platform import is_admin

LHM_PORT = 8085
LHM_URL = f"http://localhost:{LHM_PORT}/data.json"
_STARTUP_TIMEOUT = 15  # seconds to wait for /data.json readiness (.NET cold start)
_POLL_INTERVAL = 0.5  # seconds between readiness checks

# Search order for thermal sensor server binaries.
# lhm-server.exe (custom minimal server) is checked first; falling back to
# a user-installed full LibreHardwareMonitor installation.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_LHM_SEARCH_PATHS = [
    # 1. PyInstaller frozen bundle — sys._MEIPASS/tools/lhm-server.exe
    os.path.join(getattr(sys, "_MEIPASS", _PROJECT_ROOT), "tools", "lhm-server.exe"),
    # 2. Next to the running executable — portable deployment (frozen .exe)
    os.path.join(os.path.dirname(sys.executable), "tools", "lhm-server.exe"),
    # 3. Source-tree dev path — tools/lhm-server/dist/lhm-server.exe
    os.path.join(_PROJECT_ROOT, "tools", "lhm-server", "dist", "lhm-server.exe"),
    # 4. Full LibreHardwareMonitor installation (user-installed)
    os.path.join(_PROJECT_ROOT, "tools", "LibreHardwareMonitor", "LibreHardwareMonitor.exe"),
    r"C:\Program Files\LibreHardwareMonitor\LibreHardwareMonitor.exe",
    r"C:\Program Files (x86)\LibreHardwareMonitor\LibreHardwareMonitor.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\LibreHardwareMonitor\LibreHardwareMonitor.exe"),
]


def _find_elevated_pid(exe_name: str) -> Optional[int]:
    """Find the PID of a running process by exe name via tasklist."""
    try:
        result = subprocess.run(
            ["tasklist", "/fi", f"imagename eq {exe_name}", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.strip().splitlines():
            parts = line.strip('"').split('","')
            if parts and parts[0].lower() == exe_name.lower():
                return int(parts[1])
    except Exception:
        pass
    return None


def _is_port_in_use(port: int) -> bool:
    """Check if a TCP port is already bound on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _is_lhm_responding() -> bool:
    """Check if LHM's HTTP endpoint is serving valid JSON."""
    try:
        req = urllib.request.Request(LHM_URL)
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            # LHM returns a JSON object with a "Children" key at top level
            return isinstance(data, dict)
    except Exception:
        return False


def find_lhm_executable() -> tuple[Optional[str], bool]:
    """Search for a thermal sensor server binary.

    Returns:
        (path, is_custom_server) where:
        - path is the absolute path to the binary, or None if not found.
        - is_custom_server is True for lhm-server.exe (custom minimal server),
          False for the full LibreHardwareMonitor application.
    """
    for path in _LHM_SEARCH_PATHS:
        if os.path.isfile(path):
            is_custom = os.path.basename(path) == "lhm-server.exe"
            return path, is_custom
    return None, False


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

    @property
    def is_running(self) -> bool:
        """True if LHM is responding on its HTTP endpoint."""
        return _is_lhm_responding()

    def start(self) -> bool:
        """
        Launch LHM sidecar. Returns True if LHM is ready on port 8085.

        Handles three scenarios:
        1. LHM already running → attach (don't launch a second instance)
        2. Port occupied by something else → warn and skip
        3. LHM not running → launch subprocess and wait for readiness
        """
        # Scenario 1 & 2: check if port is already in use
        if _is_port_in_use(LHM_PORT):
            if _is_lhm_responding():
                print_info(
                    "LibreHardwareMonitor already running — attaching to existing instance."
                )
                self._already_running = True
                return True
            else:
                print_warning(
                    f"Port {LHM_PORT} is in use by another application — "
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
            print_warning(
                "Thermal sensor server not found. Thermal monitoring unavailable.\n"
                "  (lhm-server.exe was not bundled, and LibreHardwareMonitor is not installed)"
            )
            return False

        server_label = "lhm-server" if is_custom else "LibreHardwareMonitor"
        print_step(f"Launching {server_label} sidecar")

        # lhm-server.exe has port hardcoded to 8085 — no CLI flag needed.
        # Full LHM requires --http-port to enable its built-in web server.
        # Pass --parent-pid so lhm-server.exe self-exits when lil_bro terminates
        # (works both for direct subprocess and ShellExecuteW-elevated launches).
        parent_flag = ["--parent-pid", str(os.getpid())] if is_custom else []
        cmd = [exe] if is_custom else [exe, "--http-port", str(LHM_PORT)]

        try:
            if is_admin():
                # Running as admin — subprocess inherits the token directly.
                self._process = subprocess.Popen(
                    cmd + parent_flag,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                threading.Thread(target=self._drain_stdout, daemon=True).start()
                threading.Thread(target=self._drain_stderr, daemon=True).start()
            else:
                # Not admin — lhm-server.exe needs admin to install PawnIO on
                # first run.  Elevate via ShellExecuteW so the UAC prompt appears
                # on behalf of lhm-server.exe specifically.
                extra_args = " ".join(parent_flag)
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None,        # hwnd
                    "runas",     # verb — triggers UAC elevation
                    exe,
                    extra_args or None,
                    None,        # working directory
                    0,           # SW_HIDE
                )
                if ret <= 32:
                    print_step_done(False)
                    print_warning(
                        "Could not elevate lhm-server.exe (ShellExecuteW returned "
                        f"{ret}). Thermal monitoring unavailable."
                    )
                    return False
                self._elevated = True
        except Exception as e:
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
                action_logger.log_action(
                    "LHM Sidecar", f"Launched (PID {pid_str})", f"Port {LHM_PORT}"
                )
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
                        action_logger.log_action(
                            "LHM Sidecar",
                            "PawnIO driver activity detected",
                            line.strip(),
                        )
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

        # Timeout — process alive but HTTP never became ready
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
            # We didn't start it — don't kill it
            return
        self._kill_process()

    def _kill_process(self) -> None:
        if self._elevated:
            # lhm-server.exe was launched elevated via ShellExecuteW — we have
            # no Popen handle.  It self-exits via --parent-pid monitoring when
            # lil_bro terminates.  Best-effort kill via tasklist PID lookup.
            pid = _find_elevated_pid("lhm-server.exe")
            if pid:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        timeout=5,
                    )
                except Exception:
                    pass
            action_logger.log_action("LHM Sidecar", "Stopped (elevated)")
            self._elevated = False
            return

        if self._process is None:
            return
        pid = self._process.pid
        try:
            self._process.terminate()
            self._process.wait(timeout=3)
        except Exception:
            # terminate() timed out or was denied — try kill() then taskkill.
            # On Windows, terminate() and kill() both call TerminateProcess(); if
            # that fails (e.g. access-denied on an elevated process), fall back to
            # `taskkill /F /T` which goes through a separate OS code path and also
            # kills the full process tree.
            try:
                self._process.kill()
            except Exception:
                pass
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=5,
                )
            except Exception:
                pass
        finally:
            action_logger.log_action("LHM Sidecar", "Stopped")
            self._process = None

    def fetch_data(self) -> Optional[dict]:
        """Fetch the current sensor tree from LHM. Returns None on failure."""
        try:
            req = urllib.request.Request(LHM_URL)
            with urllib.request.urlopen(req, timeout=2) as resp:
                return json.loads(resp.read())
        except Exception:
            return None
