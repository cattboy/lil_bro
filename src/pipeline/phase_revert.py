"""Terminal UX for the 'Revert last session' flow."""

from __future__ import annotations

from datetime import datetime

from src.utils.action_logger import action_logger
from src.utils.formatting import (
    print_error,
    print_info,
    print_step,
    print_step_done,
    print_success,
    print_warning,
    prompt_approval,
)
from src.utils.revert import load_manifest, revert_fix, trigger_system_restore


def run_revert_phase() -> None:
    """Interactive revert flow — launched from menu option 4 or --revert flag."""
    manifest = load_manifest()
    if manifest is None:
        print_info(
            "no session backup found. either lil_bro hasn't run yet,\n"
            "or the last session made no changes."
        )
        return

    fixes = manifest.get("fixes", [])
    session_date = manifest.get("session_date", "unknown")

    revertible = [e for e in fixes if e.get("revertible", False)]
    non_revertible = [e for e in fixes if not e.get("revertible", False)]

    try:
        dt = datetime.fromisoformat(session_date)
        date_str = dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        date_str = session_date

    _display_summary(revertible, non_revertible, date_str)

    if not revertible:
        print_info("nothing to revert.")
        return

    if not prompt_approval(f"Revert {len(revertible)} change(s)?"):
        return

    ordered = sorted(revertible, key=lambda e: e.get("applied_at", ""))
    results: list[tuple[dict, bool, str]] = []

    print_info("\nReverting session changes...\n")
    for entry in reversed(ordered):
        fix_name = _display_name(entry.get("fix", ""))
        print_step(fix_name)
        ok, err = revert_fix(entry)
        print_step_done(success=ok)
        results.append((entry, ok, err))

    succeeded = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]

    if not failed:
        print_success("\nyou're back to factory lil_bro. everything's where you left it.")
        action_logger.log_action(
            "Revert", f"All {len(succeeded)} fix(es) reverted", session_date
        )
        return

    print_warning(f"\n{len(succeeded)} of {len(results)} changes reverted.")
    for entry, _, err in failed:
        print_error(f"  {_display_name(entry.get('fix', ''))} — {err}")

    action_logger.log_action(
        "Revert",
        f"{len(succeeded)}/{len(results)} reverted, {len(failed)} failed",
        session_date,
        outcome="PARTIAL",
    )

    print_info(
        "\nthe nuclear option is available (System Restore Point).\n"
        "it'll roll back your whole system, not just lil_bro's work."
    )
    if prompt_approval("Use System Restore Point for what's left?"):
        session_date_short = session_date[:10] if len(session_date) >= 10 else session_date
        trigger_system_restore(session_date_short)


def _display_summary(
    revertible: list[dict],
    non_revertible: list[dict],
    date_str: str,
) -> None:
    """Print the revert confirmation box."""
    inner = 52
    top_label = "─ REVERT LAST SESSION "
    top_fill = "─" * (inner - len(top_label))
    print(f"┌{top_label}{top_fill}┐")
    print(f"│{' ' * inner}│")
    found_line = f"  found your session backup from {date_str}"
    print(f"│{found_line:<{inner}}│")
    print(f"│{' ' * inner}│")

    if revertible:
        header = f"  Revertible ({len(revertible)}):"
        print(f"│{header:<{inner}}│")
        for entry in revertible:
            line = f"    {_summary_line(entry)}"
            print(f"│{line:<{inner}}│")

    if non_revertible:
        print(f"│{' ' * inner}│")
        header = f"  Cannot revert ({len(non_revertible)}):"
        print(f"│{header:<{inner}}│")
        for entry in non_revertible:
            name = _display_name(entry.get("fix", ""))
            reason = entry.get("display", entry.get("reason", "irreversible"))
            line = f"    {name:<16}{reason}"
            print(f"│{line:<{inner}}│")

    print(f"│{' ' * inner}│")
    print(f"└{'─' * inner}┘")


def _summary_line(entry: dict) -> str:
    fix = entry.get("fix", "")
    before = entry.get("before", {})
    name = _display_name(fix)

    if fix == "power_plan":
        b = before.get("name", "?")
        a = entry.get("after", {}).get("name", "?")
        return f"{name:<16}{b:<10} ← {a}"
    if fix == "game_mode":
        raw_before = before.get("AutoGameModeEnabled", 1)
        b = "OFF" if raw_before == 0 else "ON"
        raw_after = entry.get("after", {}).get("AutoGameModeEnabled", 0)
        a = "ON" if raw_after == 1 else "OFF"
        return f"{name:<16}{b:<10} ← {a}"
    if fix == "nvidia_profile":
        return f"{name:<16}.nip backup available"
    if fix == "display":
        w, h, hz = before.get("width", "?"), before.get("height", "?"), before.get("hz", "?")
        return f"{name:<16}{w}x{h}@{hz}Hz"
    return name


def _display_name(fix_key: str) -> str:
    names = {
        "power_plan": "Power Plan",
        "game_mode": "Game Mode",
        "nvidia_profile": "NVIDIA Profile",
        "display": "Display",
        "temp_folders": "Temp cleanup",
    }
    return names.get(fix_key, fix_key.replace("_", " ").title())
