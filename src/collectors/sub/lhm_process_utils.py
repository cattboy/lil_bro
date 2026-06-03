"""Low-level process introspection helpers for the LHM sidecar.

- ``_is_port_in_use`` -- TCP port liveness check via socket.
- ``_find_elevated_pid`` -- locate a running process by exe name via
  ``tasklist``; needed because a UAC-elevated LHM launch detaches from
  ``subprocess.Popen`` and only the OS knows its PID.
- ``_port_owner`` -- name the process holding a TCP port (via psutil), used to
  attribute a port-8085 collision to a specific application.

Note: re-exported via ``lhm_sidecar``. Patch through that surface so
``unittest.mock`` keeps working.
"""

import re
import socket
import subprocess
from typing import Optional

__all__ = ["_is_port_in_use", "_find_elevated_pid", "_port_owner"]

# Locks _find_elevated_pid's exe_name to safe inputs before it's interpolated
# into a tasklist /fi filter string. All current callers pass a hardcoded
# "lhm-server.exe" literal so this is defense-in-depth for a future caller
# passing config- or env-derived input.
_VALID_EXE_NAME = re.compile(r"^[\w.\-]+\.exe$")


def _find_elevated_pid(exe_name: str) -> Optional[int]:
    """Find the PID of a running process by exe name via tasklist."""
    if not _VALID_EXE_NAME.match(exe_name):
        return None  # reject malformed exe names defensively
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
        pass  # safe: tasklist parse fallback; caller treats None as "not running"
    return None


def _is_port_in_use(port: int) -> bool:
    """Check if a TCP port is already bound on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _port_owner(port: int) -> Optional[str]:
    """Return the process name holding a local TCP ``port``, or None.

    Used to name the culprit when port 8085 is occupied. Best-effort:
    ``psutil.net_connections`` raises AccessDenied without admin and can fail on
    locked-down systems, so every error collapses to None. Callers must treat
    None as "unknown owner", never as "port free".
    """
    try:
        import psutil

        for conn in psutil.net_connections(kind="inet"):
            laddr = conn.laddr
            if laddr and laddr.port == port and conn.pid:
                try:
                    return psutil.Process(conn.pid).name()
                except Exception:
                    return None  # owner vanished or denied -- unknown
    except Exception:
        return None  # psutil missing / AccessDenied / locked down
    return None
