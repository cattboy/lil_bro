"""Phase 1 — Bootstrapping & Safety: create system restore point."""

from src.pipeline.base import PipelineContext, PipelineAborted, PhaseResult
from src.bootstrapper import create_restore_point
from src.utils.formatting import print_header, print_step, print_error, prompt_approval
from src.utils.errors import LilBroError
from src.utils.debug_logger import get_debug_logger


class BootstrapPhase:
    def run(self, ctx: PipelineContext) -> PhaseResult:
        log = get_debug_logger()
        log.info("Phase 1: Bootstrapping & Safety")
        print_header("Phase 1: Bootstrapping & Safety")

        # A dashboard card fix earlier this session may have already created a
        # System Restore Point (tracked in the session manifest). Reuse it
        # rather than creating a second identically-labelled "lil_bro" entry.
        from src.utils.revert import load_manifest, mark_restore_point_created
        manifest = load_manifest()
        if manifest is not None and manifest.get("restore_point_created"):
            log.info("Phase 1: reusing restore point already created this session")
            print_step("Reusing System Restore Point created earlier this session.")
            ctx.restore_point_created = True
            return PhaseResult("completed", "Reused existing restore point")

        try:
            create_restore_point()
            ctx.restore_point_created = True
            # A dashboard fix earlier this session may have lazily created the
            # revert manifest with restore_point_created=False (no restore point
            # existed yet). Now that one does, upgrade the flag so revert can
            # honestly offer System Restore.
            mark_restore_point_created()
        except LilBroError as e:
            log.error("Restore point creation failed: %s", e)
            print_error(str(e))
            if not prompt_approval("Restore point creation failed. Continue anyway?"):
                raise PipelineAborted("User declined to continue without restore point.")
            return PhaseResult("completed", "Restore point failed — user chose to continue", error=str(e))
        return PhaseResult("completed", "Restore point created")
