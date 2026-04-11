"""Phase 1 — Bootstrapping & Safety: create system restore point."""

from src.pipeline.base import PipelineContext, PipelineAborted, PhaseResult
from src.bootstrapper import create_restore_point
from src.utils.formatting import print_header, print_error, prompt_approval
from src.utils.errors import LilBroError
from src.utils.debug_logger import get_debug_logger


class BootstrapPhase:
    def run(self, ctx: PipelineContext) -> PhaseResult:
        log = get_debug_logger()
        log.info("Phase 1: Bootstrapping & Safety")
        print_header("Phase 1: Bootstrapping & Safety")
        try:
            create_restore_point()
        except LilBroError as e:
            log.error("Restore point creation failed: %s", e)
            print_error(str(e))
            if not prompt_approval("Restore point creation failed. Continue anyway?"):
                raise PipelineAborted("User declined to continue without restore point.")
            return PhaseResult("completed", "Restore point failed — user chose to continue", error=str(e))
        return PhaseResult("completed", "Restore point created")
