"""HTTP endpoint constants and readiness probe for the LHM sidecar.

LHM exposes a JSON sensor tree at ``LHM_URL`` once it's booted. ``_is_lhm_responding``
is the cheapest possible health check -- a 2 s GET that verifies the response
is valid JSON.

Note: re-exported via ``lhm_sidecar``. External callers should import from
``lhm_sidecar``, not directly from here.
"""

import json
import urllib.request

__all__ = ["LHM_PORT", "LHM_URL", "_STARTUP_TIMEOUT", "_POLL_INTERVAL", "_is_lhm_responding"]

LHM_PORT = 8085
LHM_URL = f"http://localhost:{LHM_PORT}/data.json"
_STARTUP_TIMEOUT = 15  # seconds to wait for /data.json readiness (.NET cold start)
_POLL_INTERVAL = 0.5  # seconds between readiness checks
# Cap on a single LHM HTTP response. Defensive: if another local process
# binds port 8085 before lhm-server, an attacker-controlled body would
# otherwise be buffered into memory before json.loads. Real LHM sensor
# trees are well under 500 KB.
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024


def _is_lhm_responding() -> bool:
    """Check if LHM's HTTP endpoint is serving valid JSON."""
    try:
        req = urllib.request.Request(LHM_URL)
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read(_MAX_RESPONSE_BYTES))
            # LHM returns a JSON object with a "Children" key at top level
            return isinstance(data, dict)
    except Exception:
        return False
