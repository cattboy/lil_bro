"""Cinebench console-log score parser.

Pure regex extraction; no IO, no state. ``parse_output`` is the module
entry point and is delegated to by ``BenchmarkRunner._parse_output``.
"""

import re


def parse_output(output: str, full_suite: bool = False) -> dict[str, str]:
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
        elif "CPU_Single" not in scores:
            scores["CPU_Single"] = pts
        elif "CPU_Multi" not in scores:
            scores["CPU_Multi"] = pts
        else:
            scores[f"Score_{len(scores) + 1}"] = pts

    return scores
