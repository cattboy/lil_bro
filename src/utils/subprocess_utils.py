"""
Thin subprocess.run() wrapper with consistent timeout and debug logging.

Only covers the common subprocess.run() pattern. Popen-based patterns
(cinebench, lhm_sidecar) and polling patterns (dxdiag) stay as-is.

Window-suppression policy: lil_bro.exe is a console=False GUI build, so any
child console process spawned without CREATE_NO_WINDOW (or a hidden
STARTUPINFO) flashes a visible console window. run_subprocess() merges the
flag in automatically; direct subprocess call sites must pass
creationflags=CREATE_NO_WINDOW explicitly. Enforced repo-wide by
tests/test_no_console_window.py.
"""
import subprocess
from typing import Any

from .debug_logger import get_debug_logger

# Suppresses the console window of child console processes (sc, taskkill,
# powershell, nvidia-smi, ...). 0 on non-Windows, where the attribute doesn't
# exist and creationflags=0 is the legal default.
CREATE_NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_subprocess(
    cmd: list[str],
    *,
    timeout: int = 10,
    capture_output: bool = True,
    text: bool = True,
    check: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run a subprocess with consistent timeout and debug logging.

    Passes kwargs through to subprocess.run(). Callers are responsible
    for catching TimeoutExpired, FileNotFoundError, and CalledProcessError.

    Always merges CREATE_NO_WINDOW into creationflags (caller-supplied
    flags are OR-ed in) so child console processes never flash a console
    window -- lil_bro.exe is a console=False GUI build.

    Do not pass stdout= or stderr= alongside capture_output=True.
    """
    log = get_debug_logger()
    log.debug("subprocess: %s (timeout=%ds)", cmd, timeout)
    creationflags = kwargs.pop("creationflags", 0) | CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=capture_output,
            text=text,
            check=check,
            creationflags=creationflags,
            **kwargs,
        )
        if result.returncode != 0:
            log.debug("subprocess %s returned rc=%d", cmd[0], result.returncode)
        return result
    except subprocess.TimeoutExpired:
        log.warning("subprocess %s timed out after %ds", cmd[0], timeout)
        raise
    except FileNotFoundError:
        log.warning("subprocess %s: binary not found", cmd[0])
        raise
    except subprocess.CalledProcessError as e:
        log.warning("subprocess %s failed: rc=%d", cmd[0], e.returncode)
        raise
