"""5-phase optimization pipeline orchestrator."""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from llama_cpp import Llama  # type: ignore

from src.pipeline.base import PipelineContext, PipelineAborted, Phase
from src.pipeline.phase_bootstrap import BootstrapPhase
from src.pipeline.phase_scan import ScanPhase
from src.pipeline.phase_baseline import BaselineBenchPhase
from src.pipeline.phase_config import ConfigPhase
from src.pipeline.phase_final import FinalBenchPhase
from src.collectors.sub.lhm_sidecar import LHMSidecar
from src.benchmarks.thermal_monitor import ThermalMonitor
from src.utils.formatting import print_header

_PHASES: list[Phase] = [
    BootstrapPhase(),
    ScanPhase(),
    BaselineBenchPhase(),
    ConfigPhase(),
    FinalBenchPhase(),
]


def run_optimization_pipeline(lhm: LHMSidecar, llm: Optional[Llama] = None) -> None:
    """Top-level pipeline entry. LHM lifecycle is owned by the caller (main.py)."""
    thermal = ThermalMonitor()
    ctx = PipelineContext(lhm=lhm, thermal=thermal, llm=llm)
    try:
        for phase in _PHASES:
            phase.run(ctx)
    except PipelineAborted:
        pass
    print_header("Optimization Pipeline Complete")
