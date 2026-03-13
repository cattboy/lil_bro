Redesign Esports Check: Unified System Snapshot Architecture
Problem
The current esports check runs 6+ individual scanners sequentially, each independently calling WMI, PowerShell, or the registry with immediate console output. There is no unified data model — each scanner returns its own ad-hoc dict. This makes it impossible to:

Feed the complete system state to the LLM for intelligent analysis
Compare against a known-good "esports ready" configuration profile
Save/load/diff snapshots over time
Run all data collection in parallel for speed

Proposed Architecture
Core Concept: Collect → Snapshot → Evaluate → Report

┌──────────────────────────────────────────────────────┐
│         1. COLLECTORS (data gathering layer)          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │  WMI     │ │PowerShell│ │ Registry │ │ dxdiag  │ │
│  │ Collector│ │ Collector│ │ Collector│ │ Parser  │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬────┘ │
│       └──────┬─────┴──────┬─────┘             │      │
│              ▼            ▼                   ▼      │
│  ┌───────────────────────────────────────────────┐   │
│  │        2. SYSTEM SNAPSHOT (JSON model)         │   │
│  │  {                                            │   │
│  │    "timestamp": "...",                        │   │
│  │    "hardware": { gpu, cpu, ram, mobo },       │   │
│  │    "display": { monitors[] },                 │   │
│  │    "configuration": { game_mode, power_plan, │   │
│  │      xmp, rebar, mouse_hz },                  │   │
│  │    "software": { os_version, drivers },       │   │
│  │    "dxdiag_raw": { parsed dxdiag sections }   │   │
│  │  }                                            │   │
│  └─────────────────────┬─────────────────────────┘   │
│                        ▼                              │
│  ┌───────────────────────────────────────────────┐   │
│  │     3. EVALUATOR (rules engine)               │   │
│  │  snapshot.json  ⟷  esports_profile.json       │   │
│  │  Compare each field → PASS / WARN / FAIL      │   │
│  └─────────────────────┬─────────────────────────┘   │
│                        ▼                              │
│  ┌───────────────────────────────────────────────┐   │
│  │        4. REPORT (structured results)          │   │
│  │  { checks: [...], score: 85, grade: "B+" }    │   │
│  └───────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────┘

User Review Required
IMPORTANT

This is a significant architectural refactor. The existing scanners work — they just work one-at-a-time with print statements. This redesign separates data collection from evaluation from presentation. Before implementing we need alignment on:

Scope of data to collect — The plan below pulls WMI, registry, powercfg, dxdiag, and nvidia-smi all into one JSON snapshot. Should we also include NvidiaProfileInspector export and LibreHardwareMonitor data at this stage, or keep those for later?

How dynamic should the "esports profile" be? — Option A: A single hardcoded esports_profile.json with expected values. Option B: Multiple profiles (e.g. "casual", "competitive", "streaming") the user can select. Option C: Auto-detect hardware tier and adjust expectations accordingly. I'd recommend starting with Option A and evolving later.

Should the existing scanners be replaced or wrapped? — The current scanners have working logic and tests. My plan is to refactor them into pure data-returning collectors (strip the print/prompt logic) and keep the existing test coverage, but I want to confirm you're okay with touching all scanner files.

Mouse polling rate — This requires real-time user wiggling (3 seconds). It doesn't fit the "collect everything silently" pattern. Should we keep it as a separate interactive step, or skip it from the automated snapshot?

dxdiag integration — The projectBrief mentions running dxdiag /t dxdiag_output.txt in Phase 2. Should we implement the dxdiag parser now as part of this refactor, or stub it out?

Proposed Changes
Component 1: System Snapshot Model
[NEW] 

snapshot_schema.py
Define Python dataclasses representing the full system snapshot. These are the canonical types that all collectors populate and the evaluator consumes.

# Key sections of the snapshot:
@dataclass
class HardwareInfo:
    gpu_name: str
    gpu_vram_mb: int
    cpu_name: str
    ram_total_gb: float
    ram_speed_mhz: int
    ram_base_speed_mhz: int
    ram_modules: int

@dataclass
class DisplayInfo:
    current_refresh_rate_hz: int
    max_refresh_rate_hz: int
    resolution: str

@dataclass  
class ConfigurationInfo:
    game_mode_enabled: bool
    power_plan_name: str
    power_plan_guid: str
    xmp_enabled: bool
    rebar_enabled: bool
    rebar_bar1_size_mb: float

@dataclass
class SystemSnapshot:
    timestamp: str
    hardware: HardwareInfo
    display: DisplayInfo
    configuration: ConfigurationInfo
    # Future: dxdiag_data, nvidia_profile_data, thermal_data

NEW] 

esports_profile.json
A JSON file defining what "esports ready" looks like — the expected configuration:

{
  "profile_name": "Esports Competitive",
  "version": "1.0",
  "rules": {
    "display": {
      "min_refresh_rate_hz": 144,
      "preferred_refresh_rate_hz": 240
    },
    "configuration": {
      "game_mode_enabled": true,
      "power_plan_acceptable": ["High Performance", "Ultimate Performance"],
      "xmp_enabled": true,
      "rebar_enabled": true
    },
    "hardware": {
      "min_ram_speed_mhz_ddr4": 3200,
      "min_ram_speed_mhz_ddr5": 5600
    }
  }
}

Component 2: Collectors (Refactored Scanners)
The existing scanner files get refactored to be pure data collectors — they gather data and return it as part of the snapshot model. No print statements, no user prompts.

[MODIFY] 

display.py

get_current_refresh_rate()
 and 

get_native_refresh_rate()
 remain as-is (already pure)
Add a new collect_display_info() -> DisplayInfo that returns the model type
Keep 

check_refresh_rate()
 as a backward-compatible wrapper
[MODIFY] 

game_mode.py

get_game_mode_status()
 already returns a bool — no change needed
[MODIFY] 

power_plan.py

get_active_power_plan()
 already returns 

(guid, name)
 — no change needed
The switch/create logic stays in 

check_power_plan()
 for interactive use
[MODIFY] 

xmp_check.py

get_memory_speeds()
 already returns clean data
Add collect_xmp_info() -> dict that returns {configured_mhz, base_mhz, xmp_likely}
[MODIFY] 

rebar.py

check_nvidia_rebar()
 and 

check_wmi_rebar()
 already return tuples
Add collect_rebar_info() -> dict that returns {enabled, bar1_size_mb, method}
Component 3: Snapshot Collector (Orchestrator)
[NEW] 

system_snapshot.py
The main orchestrator that calls all collectors and assembles the SystemSnapshot:

def collect_system_snapshot() -> SystemSnapshot:
    """Collects all system information into a single snapshot."""
    # 1. Batch WMI data in one connection
    wmi_data = collect_all_wmi_data()
    
    # 2. Gather non-WMI data
    power_guid, power_name = get_active_power_plan()
    game_mode = get_game_mode_status()
    rebar_info = collect_rebar_info()
    
    # 3. Assemble and return snapshot
    return SystemSnapshot(...)

def save_snapshot(snapshot: SystemSnapshot, path: str):
    """Saves snapshot to JSON file."""

def load_snapshot(path: str) -> SystemSnapshot:
    """Loads a previously saved snapshot."""


def collect_system_snapshot() -> SystemSnapshot:
    """Collects all system information into a single snapshot."""
    # 1. Batch WMI data in one connection
    wmi_data = collect_all_wmi_data()
    
    # 2. Gather non-WMI data
    power_guid, power_name = get_active_power_plan()
    game_mode = get_game_mode_status()
    rebar_info = collect_rebar_info()
    
    # 3. Assemble and return snapshot
    return SystemSnapshot(...)

def save_snapshot(snapshot: SystemSnapshot, path: str):
    """Saves snapshot to JSON file."""

def load_snapshot(path: str) -> SystemSnapshot:
    """Loads a previously saved snapshot."""

Component 4: Evaluator (Rules Engine)
[NEW] 

evaluator.py
Compares a SystemSnapshot against an esports profile and produces a structured report:

@dataclass
class CheckResult:
    name: str           # e.g. "Refresh Rate"
    status: str         # "PASS", "WARN", "FAIL", "ERROR"
    current_value: Any  # What the system has
    expected_value: Any # What the profile says it should be
    message: str        # Human-readable explanation
    fix_available: bool # Can lil_bro fix this?

@dataclass
class EvaluationReport:
    profile_name: str
    checks: list[CheckResult]
    score: int          # 0-100 percentage
    grade: str          # A+, A, B+, B, C, D, F
    timestamp: str

def evaluate(snapshot: SystemSnapshot, profile_path: str) -> EvaluationReport:
    """Runs all checks and returns structured results."""

Component 5: Updated Main Flow
[MODIFY] 

main.py
The 

run_esports_check()
 function gets rewritten:

 def run_esports_check():
    print_header("Starting System Snapshot")
    
    # 1. Collect everything at once
    snapshot = collect_system_snapshot()
    save_snapshot(snapshot, "system_snapshot.json")
    
    # 2. Evaluate against esports profile
    report = evaluate(snapshot, "profiles/esports_profile.json")
    
    # 3. Display results
    display_report(report)
    
    # 4. Offer to fix issues (interactive - keeps human-in-the-loop)
    offer_fixes(report)

Component 6: WMI Batch Collection
[NEW] 

wmi_collector.py
Instead of creating a new WMI connection in every scanner file, make one WMI connection and batch-query everything:

def collect_all_wmi_data() -> dict:
    """Single WMI connection, multiple queries."""
    c = wmi.WMI()
    return {
        "video_controllers": [...],
        "physical_memory": [...],
        "processor": [...],
        "os": [...],
        "baseboard": [...],
        "device_memory": [...],
    }


This is a major performance win — currently we open 4+ separate WMI connections.

File Summary
Action	File	Purpose
NEW	src/models/snapshot_schema.py	Dataclass types for the snapshot
NEW	src/profiles/esports_profile.json	Expected config for "esports ready"
NEW	src/collectors/__init__.py	Package init
NEW	src/collectors/system_snapshot.py	Orchestrator that builds snapshot
NEW	src/collectors/wmi_collector.py	Batch WMI queries
NEW	src/evaluator.py	Rules engine comparing snapshot vs profile
MODIFY	

src/scanners/display.py
Add collect_display_info()
MODIFY	

src/scanners/game_mode.py
Minor — already pure
MODIFY	

src/scanners/power_plan.py
Minor — already pure
MODIFY	

src/scanners/xmp_check.py
Add collect_xmp_info()
MODIFY	

src/scanners/rebar.py
Add collect_rebar_info()
MODIFY	

src/main.py
Rewrite 

run_esports_check()
Verification Plan
Automated Tests
Since this project targets Windows (WMI, registry, PowerShell) and we develop on Linux, all tests mock Windows-specific calls. Existing tests already follow this pattern.

Run existing tests to confirm nothing breaks:
cd /home/vboxuser/Coding/lil_bro && uv run python -m pytest tests/ -v

New tests to add:

tests/test_snapshot_schema.py — Validate dataclass creation and JSON round-trip
tests/test_evaluator.py — Test evaluation with mock snapshots (PASS, WARN, FAIL for each check, grade calculation)
tests/test_system_snapshot.py — Test orchestrator with fully mocked collectors
Manual Verification
Ask user to run on their Windows machine and confirm:
The JSON snapshot file is created and contains accurate data
The evaluation report correctly flags misconfigurations
The grade/score reflects actual system state
