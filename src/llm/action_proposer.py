"""
action_proposer.py — Converts scan findings into LLM-generated action proposals.

JSON contract (see docs/office-hours-design-20260323.md):
  Input:  {"hardware": {...}, "findings": [{check, status, ...}]}
  Output: [{"finding", "severity", "explanation", "proposed_action", "can_auto_fix"}]

Fallback: if the LLM is unavailable or returns unparseable JSON, static templates
are used so the tool always produces a usable output.
"""
from __future__ import annotations
import json
from typing import Any

from src.utils.debug_logger import get_debug_logger

_SYSTEM_PROMPT = (
    "You are a gaming PC configuration assistant. You will receive a JSON object with "
    "hardware info and a list of configuration findings. For each FAIL finding, output a "
    "JSON array of action proposals. Use casual, direct language — write like a knowledgeable "
    "friend, not a manual. Do not mention checks with PASS status. Respond ONLY with a valid "
    "JSON array — no explanation text outside the JSON. Keep each explanation under 40 words."
)

_SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _is_fail(finding: dict) -> bool:
    return finding.get("status") in ("WARNING", "ERROR")


def build_llm_input(hardware: dict, findings: list[dict]) -> dict:
    """
    Maps raw findings into the contracted LLM input format.
    Only FAIL findings are included — PASS/OK findings are not sent.
    """
    llm_findings: list[dict[str, Any]] = []

    for f in findings:
        if not _is_fail(f):
            continue

        check = f.get("check", "")
        entry: dict[str, Any] = {"check": check, "status": "FAIL"}

        if check == "display":
            entry.update({
                "current_hz": f.get("current", 0),
                "max_available_hz": f.get("expected", 0),
            })
        elif check == "xmp":
            entry.update({"current_mhz": f.get("current", 0)})
        elif check == "power_plan":
            entry.update({"current_plan": f.get("current", "Unknown")})
        elif check == "game_mode":
            entry.update({"enabled": False})
        elif check == "rebar":
            entry.update({"enabled": False})
        elif check == "temp_folders":
            total_bytes = f.get("current", 0)
            entry.update({"total_mb": round(total_bytes / (1024 * 1024), 1)})
        elif check == "mouse_polling":
            entry.update({
                "current_hz": f.get("current_hz", 0),
                "threshold_hz": 500,
            })
        elif check == "thermals":
            entry.update({
                "cpu_peak": f.get("cpu_peak"),
                "gpu_peak": f.get("gpu_peak"),
            })
        elif check == "nvidia_profile":
            entry.update({
                "gpu_model": f.get("current", {}).get("gpu_model", "Unknown"),
                "missing_optimizations": [
                    s["name"] for s in f.get("sub_findings", []) if not s.get("ok")
                ],
            })

        llm_findings.append(entry)

    return {"hardware": hardware, "findings": llm_findings}


def _parse_proposals(raw: str) -> list[dict] | None:
    """Extracts the JSON array from raw LLM output. Returns None on failure."""
    raw = raw.strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        result = json.loads(raw[start : end + 1])
        return result if isinstance(result, list) else None
    except json.JSONDecodeError:
        return None


def _call_llm(llm: Any, llm_input: dict) -> list[dict] | None:
    """
    Sends findings to the model. Retries once on bad output.
    Returns a proposal list, or None if both attempts fail.
    """
    user_message = json.dumps(llm_input, indent=2)
    for _ in range(2):
        try:
            response = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=512,
                temperature=0.2,
            )
            raw = response["choices"][0]["message"]["content"]
            proposals = _parse_proposals(raw)
            if proposals is not None:
                return proposals
        except Exception:
            get_debug_logger().warning("LLM completion attempt failed", exc_info=True)
    return None


# ── Static fallback templates ──────────────────────────────────────────────────
# Used when the LLM is unavailable or returns unparseable JSON.

_FALLBACK: dict[str, dict] = {
    "display": {
        "finding": "display",
        "severity": "HIGH",
        "explanation": (
            "Your monitor is running below its maximum refresh rate. "
            "Go to Display Settings → Advanced display settings → Refresh rate "
            "and select the highest available value."
        ),
        "proposed_action": "Set refresh rate to maximum in Windows Display Settings",
        "can_auto_fix": True,
    },
    "xmp": {
        "finding": "xmp",
        "severity": "HIGH",
        "explanation": (
            "Your RAM is running at base JEDEC speed. Enable XMP or EXPO in your BIOS "
            "to unlock the rated speed — this costs 10–15% CPU performance when left off."
        ),
        "proposed_action": "Enable XMP/EXPO in BIOS (manual — requires restart)",
        "can_auto_fix": False,
    },
    "power_plan": {
        "finding": "power_plan",
        "severity": "HIGH",
        "explanation": (
            "Your power plan is throttling your CPU. High Performance keeps it at full "
            "clock speed instead of scaling down between frames."
        ),
        "proposed_action": "Switch power plan to High Performance",
        "can_auto_fix": True,
    },
    "game_mode": {
        "finding": "game_mode",
        "severity": "MEDIUM",
        "explanation": (
            "Windows Game Mode is off. It prioritizes CPU/GPU resources to the active "
            "game and reduces background jitter."
        ),
        "proposed_action": "Enable Game Mode via registry",
        "can_auto_fix": True,
    },
    "rebar": {
        "finding": "rebar",
        "severity": "MEDIUM",
        "explanation": (
            "Resizable BAR is disabled. Enable 'Above 4G Decoding' and 'Re-Size BAR Support' "
            "in BIOS for up to 10–15% GPU performance improvement in modern titles."
        ),
        "proposed_action": "Enable Resizable BAR in BIOS (manual — requires restart)",
        "can_auto_fix": False,
    },
    "temp_folders": {
        "finding": "temp_folders",
        "severity": "LOW",
        "explanation": (
            "Temp folders have over 1 GB of leftover files. Clearing them frees disk space "
            "and can reduce game shader stutter on first launch."
        ),
        "proposed_action": "Delete temporary files and shader caches",
        "can_auto_fix": True,
    },
    "mouse_polling": {
        "finding": "mouse_polling",
        "severity": "MEDIUM",
        "explanation": (
            "Your mouse polling rate is below 500Hz — this adds measurable input lag. "
            "Open your mouse's driver software and set it to 1000Hz or higher."
        ),
        "proposed_action": "Set polling rate to 1000Hz in mouse driver software (manual)",
        "can_auto_fix": False,
    },
    "thermals": {
        "finding": "thermals",
        "severity": "HIGH",
        "explanation": (
            "Your temps are running hot under load — your CPU or GPU is at risk of "
            "thermal throttling, which silently kills your FPS. Clean your fans, "
            "check your thermal paste, and make sure your case has decent airflow."
        ),
        "proposed_action": "Improve cooling: clean dust filters, check thermal paste, optimize case airflow (manual)",
        "can_auto_fix": False,
    },
    "nvidia_profile": {
        "finding": "nvidia_profile",
        "severity": "HIGH",
        "explanation": (
            "Your NVIDIA driver profile isn't optimized for gaming — G-Sync, VSync, "
            "FPS cap, and DLSS settings aren't configured for your hardware. "
            "This is like buying a sports car and leaving it in eco mode."
        ),
        "proposed_action": "Apply optimized NVIDIA driver profile (G-Sync + VSync + FPS cap + ReBar + DLSS)",
        "can_auto_fix": True,
    },
}


def _build_fallback(findings: list[dict]) -> list[dict]:
    """Returns static proposals for all FAIL findings."""
    proposals = []
    for f in findings:
        if not _is_fail(f):
            continue
        template = _FALLBACK.get(f.get("check", ""))
        if template:
            proposals.append(dict(template))
    return proposals


def propose_actions(hardware: dict, findings: list[dict], llm: Any) -> list[dict]:
    """
    Main entry point. Returns a sorted list of action proposals.

    Attempts LLM generation first; falls back to static templates on failure.
    Proposals are sorted HIGH → MEDIUM → LOW severity.
    Returns an empty list if there are no FAIL findings.
    """
    fail_findings = [f for f in findings if _is_fail(f)]
    if not fail_findings:
        return []

    proposals: list[dict] | None = None

    if llm is not None:
        llm_input = build_llm_input(hardware, fail_findings)
        proposals = _call_llm(llm, llm_input)

    if proposals is None:
        proposals = _build_fallback(fail_findings)

    proposals.sort(key=lambda p: _SEVERITY_ORDER.get(p.get("severity", "LOW"), 2))
    return proposals
