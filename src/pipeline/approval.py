"""Approval-flow utilities: proposal display, selection, and fix execution (ConfigPhase + ApplyPhase)."""

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


def run_approval_flow(proposals: list[dict], ctx) -> int:
    """
    Renders the numbered proposal list, collects batch selection, and stores
    approved proposals on ctx.approved_proposals for ApplyPhase to execute.

    Returns the count of auto-fixable proposals selected (0 = nothing approved).
    """
    from src.utils.formatting import get_batch_selection_handler

    if not proposals:
        print_success("No configuration issues found -- your setup looks good!")
        return 0

    auto_fixable = display_proposals(proposals)

    if not auto_fixable:
        print_info(
            "\nAll findings require manual BIOS/driver changes -- "
            "see the instructions above."
        )
        return 0

    total = len(proposals)
    print()

    handler = get_batch_selection_handler()
    if handler is not None:
        selection = list(handler(proposals, total) or [])
    else:
        print_prompt("Apply changes? Enter numbers (e.g. \"1 3\"), \"all\", or \"skip\": ")
        while True:
            raw = input().strip()
            selection = parse_selection(raw, total)
            if selection is not None:
                break
            print_error("Invalid input.")
            print_prompt(f"Enter numbers 1–{total}, \"all\", or \"skip\": ")

    if not selection:
        action_logger.log_approval_decision(
            [], [p.get("finding", "") for _, p in auto_fixable]
        )
        print_info("No changes applied.")
        return 0

    approved_checks = [
        proposals[n - 1].get("finding", "") for n in selection
        if proposals[n - 1].get("can_auto_fix")
    ]
    skipped_checks = [
        p.get("finding", "") for _, p in auto_fixable
        if p.get("finding") not in approved_checks
    ]
    action_logger.log_approval_decision(approved_checks, skipped_checks)

    selected_proposals = {n: p for n, p in auto_fixable if n in selection}
    for n in selection:
        proposal = proposals[n - 1]
        if not proposal.get("can_auto_fix") and n not in selected_proposals:
            print_info(
                f"[{proposal.get('finding')}] Manual action required: "
                f"{proposal.get('proposed_action')}"
            )

    ctx.approved_proposals = [p for _, p in sorted(selected_proposals.items())]
    return len(ctx.approved_proposals)


def execute_approved_fixes(ctx) -> int:
    """Execute proposals stored by run_approval_flow. Sets ctx.fixes_applied and returns count.

    Called by ApplyPhase. Always runs regardless of benchmark state.
    """
    if not ctx.approved_proposals:
        return 0

    bar = AnimatedProgressBar(total=len(ctx.approved_proposals), label="Applying fixes")

    try:
        from src.utils.revert import start_session_manifest
        start_session_manifest(restore_point_created=ctx.restore_point_created)
    except Exception:
        from src.utils.formatting import print_warning
        print_warning("Revert will not be available for this session — backup could not be saved.")

    bar.start()

    applied = 0
    for i, proposal in enumerate(ctx.approved_proposals, 1):
        check = proposal.get("finding", "")
        bar.update(i, f"Fixing {check.replace('_', ' ')}...")
        if execute_fix(check, ctx.specs):
            applied += 1

    bar.finish()

    print_info(
        "\nIf anything looks wrong, a System Restore Point was created at startup. "
        "Open 'Create a restore point' in Windows to roll back."
    )
    ctx.fixes_applied = applied
    return applied
