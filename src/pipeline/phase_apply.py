"""Phase 6 — Apply Fixes: execute approved proposals from ConfigPhase.

Always runs unconditionally — fixes are applied regardless of benchmark state.
"""

from src.pipeline.base import PipelineContext, PhaseResult
from src.pipeline.approval import execute_approved_fixes
from src.utils.formatting import print_header, print_info
from src.utils.debug_logger import get_debug_logger


class ApplyPhase:
    def run(self, ctx: PipelineContext) -> PhaseResult:
        log = get_debug_logger()
        log.info("Phase 6: Apply Fixes")
        print_header("Phase 6: Apply Fixes")

        if not ctx.approved_proposals:
            print_info("No changes to apply.")
            return PhaseResult("skipped", "No approved proposals")

        applied = execute_approved_fixes(ctx)
        log.info("Applied %d fix(es)", applied)
        return PhaseResult("completed", f"{applied} fix(es) applied")
