"""
Pipeline base types — PipelineContext and Phase Protocol.

PipelineContext is a plain dataclass that carries shared state between phases.
Phase is a structural Protocol — any class with a run(ctx) method qualifies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Protocol

if TYPE_CHECKING:
    from src.collectors.sub.lhm_sidecar import LHMSidecar
    from src.benchmarks.thermal_monitor import ThermalMonitor
    from src.benchmarks.cinebench import BenchmarkRunner


class PipelineAborted(Exception):
    """Raised by a Phase to cleanly stop the pipeline (e.g. user declined restore point)."""


@dataclass
class PipelineContext:
    """Shared state bag passed between all pipeline phases."""

    # Set at construction — owned by main.py's finally block
    lhm: "LHMSidecar"
    thermal: "ThermalMonitor"

    # Optional LLM instance — None when model isn't loaded
    llm: object = None

    # Set by ScanPhase
    lhm_available: bool = False
    specs: dict = field(default_factory=dict)

    # Set by BaselineBenchPhase
    runner: Optional["BenchmarkRunner"] = None
    baseline_result: dict = field(default_factory=dict)
    peak_temps: dict = field(default_factory=dict)


class Phase(Protocol):
    """Structural protocol for pipeline phases."""

    def run(self, ctx: PipelineContext) -> None: ...
