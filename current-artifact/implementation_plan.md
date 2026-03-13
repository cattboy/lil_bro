# Implementation Plan: Workflow-First Esports PC Optimization Pipeline

## Core Requirements & Changes (Based on User Feedback)

1. **Workflow-First approach**: Build the end-to-end pipeline *without* the local LLM agent first. The LLM will be added later to interact and double-check results.
2. **Keep Old Settings Configurations**: Do not delete the old WMI/PowerShell configurations setting scripts. They must remain as "tools" for the future agent.
3. **Consolidate 5 Spec Sources**: Gather data from WMI, DXDiag (XML), LibreHardwareMonitor (CLI/Lib), `nvidia-smi` (CLI), and `amdsmi` (Python lib).
4. **Benchmarking Loop**:
   - Collect Baseline Specs
   - Benchmark (Cinebench 2026 CPU & GPU)
   - Apply Esports Settings (Debloat, configuration tweaks) + Log all changes
   - Benchmark again
   - Compare and Report

## Proposed Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                    LIL' BRO ORCHESTRATOR                      │
│                                                               │
│  1. COLLECT SPECS                                             │
│     WMI + DXDiag(XML) + LHM(Lib) + nvidia-smi + amdsmi        │
│          └─> Save to full_specs.json                          │
│                                                               │
│  2. INITIAL BENCHMARK                                         │
│     Run Cinebench 2026 (CPU/GPU)                              │
│          └─> Save baseline score + peak temps                 │
│                                                               │
│  3. APPLY ESPORTS FIXES ("The Tools")                         │
│     [Existing PowerPlan, ReBAR, GameMode, TempAudit, etc.]    │
│          └─> Save to actions_log.txt                          │
│                                                               │
│  4. FINAL BENCHMARK                                           │
│     Run Cinebench 2026                                        │
│          └─> Save final score + peak temps                    │
│                                                               │
│  5. VERIFY & REPORT                                           │
│     Compare start vs end. Flag >90°C thermal issues.          │
└───────────────────────────────────────────────────────────────┘
```

## Phase 1: Data Collection & Consolidation

Create an orchestrator script to generate `full_specs.json`.

**New File: `src/collectors/spec_dumper.py`**
- **WMI**: Batch query `Win32_OperatingSystem`, `Win32_Processor`, `Win32_PhysicalMemory`, `Win32_BaseBoard`, `Win32_BIOS`.
- **DXDiag**: Call `subprocess.run(["dxdiag", "/x", "C:\\Temp\\dxdiag.xml"])`, wait, then parse via `xml.etree.ElementTree`.
- **NVIDIA SMI**: Call `nvidia-smi --query-gpu=... --format=csv` as per user example to get Name, VRAM, BAR1, Temp, Driver.
- **AMD SMI**: Leverage the AMD SMI Python API (`amdsmi`) if available, or fallback to parsing `amd-smi` CLI output or registry for ReBAR and GPU config.
- **LibreHardwareMonitor**: We will trigger the LHM library (headless) to dump sensor data to JSON and merge it into our spec file.

## Phase 2: Benchmarking Orchestration

**New File: `src/benchmarks/cinebench.py`**
- Create wrappers to silently trigger Cinebench 2026 using its CLI flags: `start /b /wait "parentconsole" Cinebench.exe g_CinebenchAllTests=true g_CinebenchCpuXTest=true`
- Parse the resulting output logs (or console capture) to extract the CPU Multicore/Singlecore and GPU scores.
- While the benchmark runs, monitor peak temperatures via LHM.

## Phase 3: Esports Fix Configurator & Action Logger

**Modify Existing Files:** (e.g. `src/scanners/power_plan.py`, `rebar.py`, `temp_audit.py`)
- The existing interactive scanners/fixers remain largely intact, but we add an **Action Logger**.
- **New File: `src/utils/action_logger.py`**: Every time a PowerShell command or Registry edit is made by one of our tools, it is appended to `C:\Temp\lil_bro_actions.log` with a timestamp.

**Example Tool Update (`src/scanners/power_plan.py`)**:
```python
def set_active_plan(guid: str) -> None:
    subprocess.run(["powercfg", "/setactive", guid], check=True)
    action_logger.log_action("PowerCfg", f"Switched power plan to {guid}")
```

## Phase 4: Workflow Orchestration

**Rewrite `src/main.py`** to handle the sequential pipeline:
1. Print Banner
2. Call `spec_dumper.py` -> `full_specs.json`
3. Call `cinebench.py` -> baseline score
4. Run all Esports fixers sequentially (user prompt to confirm each, or confirm batch). All actions logged to `actions_log.txt`.
5. Call `cinebench.py` -> final score
6. Output comparison table:
   - "Baseline Score: X -> Final Score: Y (+Z%)"
   - "Max CPU Temp: Y°C (Warning! >90°C)"

## Action Plan

If this plan looks complete and correct, we will execute it in the following order:

1. Build `src/collectors/spec_dumper.py` and `src/utils/action_logger.py` first.
2. Build `src/benchmarks/cinebench.py`.
3. Update the existing `src/scanners/` scripts to wire into the `action_logger.py`.
4. Tie the workflow together in `src/main.py`.
