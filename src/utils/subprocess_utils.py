"""
Thin subprocess.run() wrapper with consistent timeout and debug logging.

Only covers the common subprocess.run() pattern. Popen-based patterns
(cinebench, lhm_sidecar) and polling patterns (dxdiag) stay as-is.
"""
import subprocess
from typing import Any

from .debug_logger import get_debug_logger


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

    Do not pass stdout= or stderr= alongside capture_output=True.
    """
    log = get_debug_logger()
    log.debug("subprocess: %s (timeout=%ds)", cmd, timeout)
    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=capture_output,
            text=text,
            check=check,
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
