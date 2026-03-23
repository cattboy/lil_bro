"""
LibreHardwareMonitor sidecar process manager.

Launches LHM as a background process with its HTTP server on port 8085,
waits for readiness, and tears down on exit. Gracefully degrades if LHM
is unavailable or the port is occupied.
"""

import json
import os
import socket
import subprocess
import time
import urllib.request
from typing import Optional

from ...utils.formatting import print_step, print_step_done, print_warning, print_info
from ...utils.action_logger import action_logger

LHM_PORT = 8085
LHM_URL = f"http://localhost:{LHM_PORT}/data.json"
_STARTUP_TIMEOUT = 5  # seconds to wait for /data.json readiness
_POLL_INTERVAL = 0.5  # seconds between readiness checks

# Common install paths for LibreHardwareMonitor
_LHM_SEARCH_PATHS = [
    # Bundled with lil_bro (future installer)
    os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")),
        "tools",
        "LibreHardwareMonitor",
        "LibreHardwareMonitor.exe",
    ),
    # User-installed common locations
    r"C:\Program Files\LibreHardwareMonitor\LibreHardwareMonitor.exe",
    r"C:\Program Files (x86)\LibreHardwareMonitor\LibreHardwareMonitor.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\LibreHardwareMonitor\LibreHardwareMonitor.exe"),
]


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


def find_lhm_executable() -> Optional[str]:
    """Search common paths for the LHM executable. Returns path or None."""
    for path in _LHM_SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    return None


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

        # Scenario 3: find and launch LHM
        exe = self._exe_path or find_lhm_executable()
        if not exe:
            print_warning(
                "LibreHardwareMonitor not found. Thermal monitoring unavailable.\n"
                "  Install from: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases"
            )
            return False

        print_step("Launching LibreHardwareMonitor sidecar")
        try:
            # Launch with HTTP server enabled.
            # LHM CLI: --http-port sets the web server port.
            self._process = subprocess.Popen(
                [exe, "--http-port", str(LHM_PORT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as e:
            print_step_done(False)
            print_warning(f"Failed to launch LibreHardwareMonitor: {e}")
            return False

        # Wait for HTTP readiness
        deadline = time.monotonic() + _STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if _is_lhm_responding():
                print_step_done(True)
                action_logger.log_action(
                    "LHM Sidecar", f"Launched (PID {self._process.pid})", f"Port {LHM_PORT}"
                )
                return True
            time.sleep(_POLL_INTERVAL)

        # Timeout — LHM started but HTTP never became ready
        print_step_done(False)
        print_warning(
            f"LibreHardwareMonitor launched but /data.json not reachable after "
            f"{_STARTUP_TIMEOUT}s. Thermal monitoring unavailable."
        )
        self._kill_process()
        return False

    def stop(self) -> None:
        """Tear down the LHM sidecar if we launched it."""
        if self._already_running:
            # We didn't start it — don't kill it
            return
        self._kill_process()

    def _kill_process(self) -> None:
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
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
