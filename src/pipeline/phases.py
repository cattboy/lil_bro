"""5-phase optimization pipeline orchestrator."""

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


def run_optimization_pipeline(lhm: LHMSidecar, llm: object = None) -> None:
    """Top-level pipeline entry. LHM lifecycle is owned by the caller (main.py)."""
    thermal = ThermalMonitor()
    ctx = PipelineContext(lhm=lhm, thermal=thermal, llm=llm)
    try:
        for phase in _PHASES:
            phase.run(ctx)
    except PipelineAborted:
        pass
    print_header("Optimization Pipeline Complete")
