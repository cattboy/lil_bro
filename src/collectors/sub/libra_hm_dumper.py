"""
LibreHardwareMonitor data collector.

Fetches the full sensor tree from LHM's HTTP endpoint. Uses the sidecar
module for the actual HTTP call so there's a single source of truth for
the connection details.
"""

from .lhm_sidecar import LHM_URL

import json
import urllib.request


def get_lhm_data() -> dict | str:
    """
    Fetch the full LHM sensor tree from localhost:8085/data.json.

    Returns the parsed JSON dict on success, or an error string on failure.
    Called during Phase 2 (Deep System Scan) by spec_dumper.
    """
    try:
        req = urllib.request.Request(LHM_URL)
        with urllib.request.urlopen(req, timeout=2) as response:
            return json.loads(response.read())
    except Exception as e:
        return f"LibreHardwareMonitor not reachable at localhost:{8085} ({e})"
