"""Phase 4 approval flow -- proposal display, selection parsing, and fix execution."""

from src.utils.action_logger import action_logger
from src.utils.formatting import (
    print_info, print_error, print_success, print_prompt, print_proposal,
)
from src.utils.progress_bar import AnimatedProgressBar
from src.pipeline.fix_dispatch import execute_fix


def display_proposals(proposals: list[dict]) -> list[tuple[int, dict]]:
    """
    Prints the numbered proposal list.

    Returns only auto-fixable proposals as [(number, proposal), ...]
    so the caller knows which numbers to offer.
    """
    auto_fixable: list[tuple[int, dict]] = []
    num = 0

    for proposal in proposals:
        can_fix = proposal.get("can_auto_fix", False)
        num += 1
        print_proposal(
            num=num,
            severity=proposal.get("severity", "MEDIUM"),
            title=proposal.get("finding", "").replace("_", " ").title(),
            explanation=proposal.get("explanation", ""),
            action=proposal.get("proposed_action", ""),
            can_auto_fix=can_fix,
        )
        if can_fix:
            auto_fixable.append((num, proposal))

    return auto_fixable


def parse_selection(raw: str, max_num: int) -> list[int] | None:
    """
    Parses the user's batch selection string.

    Returns a list of 1-based integers, an empty list for "skip",
    or None if input is invalid.
    """
    raw = raw.strip().lower()
    if raw in ("skip", "s", ""):
        return []
    if raw == "all":
        return list(range(1, max_num + 1))
    try:
        nums = [int(t) for t in raw.split()]
        if all(1 <= n <= max_num for n in nums):
            return nums
    except ValueError:
        pass
    return None


def run_approval_flow(proposals: list[dict], specs: dict, restore_point_created: bool = False) -> None:
    """
    Renders the numbered proposal list, collects batch selection,
    and executes approved auto-fixable actions.
    """
    if not proposals:
        print_success("No configuration issues found -- your setup looks good!")
        return

    auto_fixable = display_proposals(proposals)

    if not auto_fixable:
        print_info(
            "\nAll findings require manual BIOS/driver changes -- "
            "see the instructions above."
        )
        return

    total = len(proposals)
    print()
    print_prompt(f"Apply changes? Enter numbers (e.g. \"1 3\"), \"all\", or \"skip\": ")

    while True:
        raw = input().strip()
        selection = parse_selection(raw, total)
        if selection is not None:
            break
        print_error("Invalid input.")
        print_prompt(f"Enter numbers 1\u2013{total}, \"all\", or \"skip\": ")

    if not selection:
        action_logger.log_approval_decision(
            [], [p.get("finding", "") for _, p in auto_fixable]
        )
        print_info("No changes applied.")
        return

    # Determine which auto-fixable checks were approved vs skipped
    approved_checks = [
        proposals[n - 1].get("finding", "") for n in selection
        if proposals[n - 1].get("can_auto_fix")
    ]
    skipped_checks = [
        p.get("finding", "") for _, p in auto_fixable
        if p.get("finding") not in approved_checks
    ]
    action_logger.log_approval_decision(approved_checks, skipped_checks)

    # Map selected numbers to proposals
    selected_proposals = {n: p for n, p in auto_fixable if n in selection}
    # Inform about manual-only selections
    for n in selection:
        proposal = proposals[n - 1]
        if not proposal.get("can_auto_fix") and n not in selected_proposals:
            print_info(
                f"[{proposal.get('finding')}] Manual action required: "
                f"{proposal.get('proposed_action')}"
            )

    print()
    bar = AnimatedProgressBar(total=len(selected_proposals), label="Applying fixes")

    # Start session manifest before fix loop so each fix can append its backup entry
    try:
        from src.utils.revert import start_session_manifest
        start_session_manifest(restore_point_created=restore_point_created)
    except Exception:
        from src.utils.formatting import print_warning
        print_warning("Revert will not be available for this session — backup could not be saved.")

    bar.start()

    for i, (_n, proposal) in enumerate(sorted(selected_proposals.items()), 1):
        check = proposal.get("finding", "")
        bar.update(i, f"Fixing {check.replace('_', ' ')}...")
        execute_fix(check, specs)

    bar.finish()

    print_info(
        "\nIf anything looks wrong, a System Restore Point was created at startup. "
        "Open 'Create a restore point' in Windows to roll back."
    )
