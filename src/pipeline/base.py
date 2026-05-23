"""
Pipeline base types — PipelineContext and Phase Protocol.

PipelineContext is a plain dataclass that carries shared state between phases.
Phase is a structural Protocol — any class with a run(ctx) method qualifies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Optional, Protocol

if TYPE_CHECKING:
    from src.collectors.sub.lhm_sidecar import LHMSidecar
    from src.benchmarks.thermal_monitor import ThermalMonitor
    from src.benchmarks.cinebench import BenchmarkRunner
    from llama_cpp import Llama  # type: ignore


class PipelineAborted(Exception):
    """Raised by a Phase to cleanly stop the pipeline (e.g. user declined restore point)."""


@dataclass
class PhaseResult:
    """Return value from Phase.run() — gives the orchestrator visibility into phase outcomes."""

    status: Literal["completed", "skipped", "failed"]
    message: str = ""
    error: Optional[str] = None


@dataclass
class PipelineContext:
    """Shared state bag passed between all pipeline phases."""

    # Set at construction — owned by main.py's finally block
    lhm: "LHMSidecar"
    thermal: "ThermalMonitor"

    # Optional LLM instance — None when model isn't loaded
    llm: Optional[Llama] = None

    # Set by ScanPhase
    lhm_available: bool = False
    specs: dict = field(default_factory=dict)

    # Set by BaselineBenchPhase
    runner: Optional["BenchmarkRunner"] = None
    baseline_result: dict = field(default_factory=dict)
    peak_temps: dict = field(default_factory=dict)

    # Set by BootstrapPhase — whether a System Restore Point was created
    restore_point_created: bool = False

    # Set by ConfigPhase — count of auto-fixes successfully applied this run.
    # FinalBenchPhase skips when this is 0 (nothing changed to benchmark against).
    fixes_applied: int = 0

    # Set by ScanPhase — mouse polling measured before spec dump in GUI mode
    mouse_result: Optional[dict] = None

    # Set by BenchmarkOptInPhase — True/False = user's explicit choice; None = not decided.
    run_benchmarks: Optional[bool] = None

    # Set by ConfigPhase — approved proposals pending execution in ApplyPhase.
    approved_proposals: list = field(default_factory=list)

    # Set by BaselineBenchPhase when user declines to apply after a benchmark abort.
    skip_apply: bool = False

    # Set by BaselineBenchPhase when user confirms apply despite benchmark abort.
    # Phases loop honours this to not break on is_cancelled().
    cancel_override: bool = False


class Phase(Protocol):
    """Structural protocol for pipeline phases."""

    def run(self, ctx: PipelineContext) -> PhaseResult: ...
