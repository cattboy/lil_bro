# Refactor main.py — Full Module Split Implementation Plan

**Date:** 2026-03-25
**Target:** Split `src/main.py` (549 lines) into `src/pipeline/` package
**Result:** main.py becomes ~48-line entry point; 7 new pipeline modules; 3 new test files (~28 tests)

---

## Current State

`src/main.py` has 4 responsibility groups, a duplicated thermal safety gate, an if-elif dispatch chain, and zero test coverage:

| Group | Lines | Functions |
|-------|-------|-----------|
| Banner + Menu | 42-129 | `print_banner()`, `menu_loop()`, `setup_ai_model()` |
| Phase 4 Approval Flow | 131-311 | `_display_proposals()`, `_parse_selection()`, `_execute_fix()`, `_run_approval_flow()` |
| 5-Phase Pipeline | 315-519 | `run_optimization_pipeline()`, `_run_pipeline()` |
| Entry Point | 521-549 | `main()` |

---

## New File Structure

```
src/
  main.py                    <- REWRITTEN: ~48 lines (entry point only)
  pipeline/
    __init__.py              <- Empty package marker
    _state.py                <- Shared _llm state (get_llm/set_llm)
    banner.py                <- print_banner()
    menu.py                  <- menu_loop(), setup_ai_model()
    approval.py              <- display_proposals, parse_selection, run_approval_flow
    fix_dispatch.py          <- FIX_REGISTRY dict + execute_fix()
    thermal_gate.py          <- Deduplicated thermal safety gate helper
    phases.py                <- run_optimization_pipeline, _run_pipeline
tests/
  test_parse_selection.py    <- NEW: 12 tests
  test_thermal_gate.py       <- NEW: 6 tests
  test_fix_dispatch.py       <- NEW: 10 tests
```

**Import dependency graph (no cycles):**
```
main.py -> pipeline.banner
        -> pipeline.menu -> pipeline.phases -> pipeline.approval -> pipeline.fix_dispatch
                                            -> pipeline.thermal_gate
                                            -> pipeline._state
                         -> pipeline._state
```

`_state.py` imports nothing from `src/` — it's the firewall that prevents circular imports.

---

## Step-by-Step Implementation

### Step 1: Create `src/pipeline/__init__.py` and `src/pipeline/_state.py`

Create the directory and two files. Nothing else references these yet.

**`src/pipeline/__init__.py`** — empty file:
```python
```

**`src/pipeline/_state.py`**:
```python
"""
Shared mutable state for the pipeline.

The LLM instance is loaded once via the AI Setup menu and reused
across pipeline runs. Storing it here avoids circular imports
between menu.py and phases.py.

IMPORTANT: Never write `from src.pipeline._state import _llm` — that
creates a local binding that never sees updates. Always use the
getter/setter functions.
"""

_llm = None


def get_llm():
    """Returns the current LLM instance (may be None)."""
    return _llm


def set_llm(instance):
    """Sets the LLM instance after loading."""
    global _llm
    _llm = instance
```

---

### Step 2: Create `src/pipeline/banner.py`

Direct copy of `print_banner()` from main.py lines 42-52.

```python
"""ASCII art banner and tagline."""

from colorama import Fore, Style
from src.utils.formatting import print_accent, print_dim


def print_banner():
    """Prints the lil_bro ASCII art banner with tagline and privacy notice."""
    banner = f"""{Fore.MAGENTA}{Style.BRIGHT}
   _   _    __  _           ___
 | | (_)  / / | |__   _ __ / _ \\
 | | | | / /  | '_ \\ | '__| | | |
 | | | |/ /   | |_) || |  | |_| |
 |_| |_/_/    |_.__/ |_|   \\___/
{Style.RESET_ALL}"""
    print(banner)
    print_accent("  Your Local AI PC Optimization Agent")
    print_dim("  Privacy Guarantee: 100% Offline Analysis. No data leaves your machine.\n")
```

---

### Step 3: Create `src/pipeline/thermal_gate.py`

Deduplicates the 14-line thermal safety gate pattern that appears in Phase 3 (lines 367-380) and Phase 5 (lines 486-500) of the current `_run_pipeline`.

```python
"""Shared thermal safety gate -- used before both benchmark phases."""

from src.benchmarks.thermal_monitor import fetch_snapshot
from src.agent_tools.thermal_guidance import check_idle_thermals
from src.utils.formatting import print_info, print_success, print_warning, prompt_approval


def thermal_safety_gate(
    lhm_available: bool,
    skip_message: str = "Skipping benchmark -- let your PC cool down and try again.",
    approval_prompt: str = "Temperatures are elevated. Run the benchmark anyway?",
) -> bool:
    """
    Checks idle thermals before a benchmark run.

    Args:
        lhm_available: Whether LHM sidecar is running.
        skip_message: Message to print if user declines.
        approval_prompt: The prompt shown when temps are elevated.

    Returns:
        True if the benchmark should be SKIPPED, False if safe to proceed.
    """
    if not lhm_available:
        return False  # No thermal data -- proceed

    print_info("Checking idle temperatures before benchmark...")
    idle_temps = fetch_snapshot()
    idle_check = check_idle_thermals(idle_temps)

    if idle_check["safe"]:
        print_success(idle_check["message"])
        return False  # Safe -- don't skip

    print_warning(idle_check["message"])
    if not prompt_approval(approval_prompt):
        print_info(skip_message)
        return True  # User chose to skip

    return False  # User approved despite high temps
```

**Return value convention:** `True` = skip the benchmark, `False` = proceed. Matches the existing `benchmark_skipped`/`final_skipped` variable semantics.

---

### Step 4: Create `src/pipeline/fix_dispatch.py`

Replaces the `_execute_fix` if-elif chain (main.py lines 178-247) with a dispatch dict pattern. Each handler has a uniform `(specs: dict) -> bool` signature.

```python
"""
Fix dispatch registry -- maps check names to executable fix functions.

Each fix handler has the signature: (specs: dict) -> bool
To add a new auto-fixable check, add one handler function and one dict entry.
"""

from src.utils.formatting import print_success, print_error


def _fix_display(specs: dict) -> bool:
    """Sets monitor to highest available refresh rate."""
    from src.collectors.sub.monitor_dumper import get_all_displays
    from src.agent_tools.display_setter import find_best_mode, apply_display_mode

    try:
        devices = get_all_displays()
        device = devices[0] if devices else "\\\\.\\DISPLAY1"
        mode = find_best_mode(device, target_hz=None, require_same_resolution=True)
        if mode is None:
            print_error("[display] No suitable mode found -- nothing changed.")
            return False
        ok, msg = apply_display_mode(device, mode, persist=True, dry_run=True)
        if not ok:
            print_error(f"[display] Validation failed: {msg}")
            return False
        ok, msg = apply_display_mode(device, mode, persist=True, dry_run=False)
        if ok:
            print_success(
                f"[display] Refresh rate set to {mode.dmDisplayFrequency}Hz "
                f"({mode.dmPelsWidth}x{mode.dmPelsHeight}). {msg}"
            )
        else:
            print_error(f"[display] Apply failed: {msg}")
        return ok
    except Exception as e:
        print_error(f"[display] Error: {e}")
        return False


def _fix_power_plan(specs: dict) -> bool:
    """Switches to a high-performance power plan."""
    from src.agent_tools.power_plan import (
        list_available_plans, set_active_plan,
        create_high_performance_plan, _PERF_GUIDS,
    )

    try:
        plans = list_available_plans()
        target = next((p for p in plans if p[0] in _PERF_GUIDS), None)
        if not target:
            target = next(
                (p for p in plans if "performance" in p[1].lower()), None
            )
        if target:
            guid, name = target
        else:
            guid, name = create_high_performance_plan()
        set_active_plan(guid)
        print_success(f"[power_plan] Switched to '{name}'.")
        return True
    except Exception as e:
        print_error(f"[power_plan] Failed: {e}")
        return False


def _fix_temp_folders(specs: dict) -> bool:
    """Cleans temporary file directories."""
    from src.agent_tools.temp_audit import clean_temp_folders

    details = specs.get("TempFolders", {}).get("details", {})
    try:
        clean_temp_folders(details)
        return True
    except Exception as e:
        print_error(f"[temp_folders] Cleanup failed: {e}")
        return False


def _fix_game_mode(specs: dict) -> bool:
    """Enables Windows Game Mode via registry."""
    from src.agent_tools.game_mode import set_game_mode

    try:
        set_game_mode(enabled=True)
        print_success("[game_mode] Game Mode enabled.")
        return True
    except Exception as e:
        print_error(f"[game_mode] Failed: {e}")
        return False


# ---- Dispatch Registry ----
# Key: check name (matches proposal["finding"])
# Value: callable with signature (specs: dict) -> bool
FIX_REGISTRY: dict[str, callable] = {
    "display": _fix_display,
    "power_plan": _fix_power_plan,
    "temp_folders": _fix_temp_folders,
    "game_mode": _fix_game_mode,
}


def execute_fix(check: str, specs: dict) -> bool:
    """
    Executes the auto-fix for a given check name.

    Looks up the check in FIX_REGISTRY and calls the handler.
    Returns True on success, False if the check is unknown or the fix fails.
    """
    handler = FIX_REGISTRY.get(check)
    if handler is None:
        return False
    return handler(specs)
```

**Note on lazy imports:** Each handler uses lazy imports inside the function body. This avoids loading Win32 ctypes modules at import time and simplifies testing. However, this means patch targets must use the original module path (e.g., `@patch("src.agent_tools.game_mode.set_game_mode")`). If you prefer simpler patching, move imports to the top of the file — since `fix_dispatch.py` is only imported when the pipeline runs, startup cost is not a concern.

---

### Step 5: Create `src/pipeline/approval.py`

Moves the 4 Phase 4 helper functions from main.py (lines 131-311). Leading underscores are dropped since these are now the public API of the approval module.

```python
"""Phase 4 approval flow -- proposal display, selection parsing, and fix execution."""

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


def run_approval_flow(proposals: list[dict], specs: dict) -> None:
    """
    Renders the numbered proposal list, collects batch selection,
    and executes approved auto-fixable actions.
    """
    if not proposals:
        print_success("No configuration issues found -- your setup looks good!")
        return

    auto_fixable = display_proposals(proposals)

    if not auto_fixable:
        print_info(
            "\nAll findings require manual BIOS/driver changes -- "
            "see the instructions above."
        )
        return

    total = len(proposals)
    print()
    print_prompt(f"Apply changes? Enter numbers (e.g. \"1 3\"), \"all\", or \"skip\": ")

    while True:
        raw = input().strip()
        selection = parse_selection(raw, total)
        if selection is not None:
            break
        print_error("Invalid input.")
        print_prompt(f"Enter numbers 1\u2013{total}, \"all\", or \"skip\": ")

    if not selection:
        print_info("No changes applied.")
        return

    # Map selected numbers to proposals
    selected_proposals = {n: p for n, p in auto_fixable if n in selection}
    # Inform about manual-only selections
    for n in selection:
        proposal = proposals[n - 1]
        if not proposal.get("can_auto_fix") and n not in selected_proposals:
            print_info(
                f"[{proposal.get('finding')}] Manual action required: "
                f"{proposal.get('proposed_action')}"
            )

    print()
    bar = AnimatedProgressBar(total=len(selected_proposals), label="Applying fixes")
    bar.start()

    for i, (_n, proposal) in enumerate(sorted(selected_proposals.items()), 1):
        check = proposal.get("finding", "")
        bar.update(i, f"Fixing {check.replace('_', ' ')}...")
        execute_fix(check, specs)

    bar.finish()

    print_info(
        "\nIf anything looks wrong, a System Restore Point was created at startup. "
        "Open 'Create a restore point' in Windows to roll back."
    )
```

---

### Step 6: Create `src/pipeline/phases.py`

Moves `run_optimization_pipeline()` and `_run_pipeline()` from main.py (lines 315-519). Key changes from original:
- `_llm` accessed via `get_llm()` instead of module-level variable
- Thermal safety gates call `thermal_safety_gate()` instead of inline code
- Approval flow calls `run_approval_flow()` from approval.py

```python
"""5-phase optimization pipeline orchestrator."""

import json

from src.bootstrapper import create_restore_point
from src.agent_tools.display import analyze_display
from src.agent_tools.game_mode import analyze_game_mode
from src.agent_tools.power_plan import analyze_power_plan
from src.agent_tools.xmp_check import analyze_xmp
from src.agent_tools.rebar import analyze_rebar
from src.agent_tools.temp_audit import analyze_temp_folders
from src.agent_tools.mouse import check_polling_rate
from src.agent_tools.thermal_guidance import analyze_thermals
from src.collectors.spec_dumper import dump_system_specs
from src.collectors.sub.lhm_sidecar import LHMSidecar
from src.benchmarks.cinebench import BenchmarkRunner
from src.benchmarks.thermal_monitor import ThermalMonitor
from src.utils.dump_parser import extract_hardware_summary
from src.llm.action_proposer import propose_actions
from src.utils.formatting import (
    print_header, print_info, print_warning, print_error,
    print_success, print_accent, print_dim, print_prompt,
    print_key_value, print_audit_summary, print_finding,
    prompt_approval,
)
from src.utils.errors import LilBroError
from src.pipeline._state import get_llm
from src.pipeline.thermal_gate import thermal_safety_gate
from src.pipeline.approval import run_approval_flow


def run_optimization_pipeline():
    """Top-level pipeline entry. Manages LHM sidecar lifecycle."""
    lhm = LHMSidecar()
    thermal = ThermalMonitor()

    try:
        _run_pipeline(lhm, thermal)
    finally:
        lhm.stop()


def _run_pipeline(lhm: LHMSidecar, thermal: ThermalMonitor):
    """Executes all 5 phases sequentially."""

    # -- Phase 1: Bootstrapping & Safety --
    print_header("Phase 1: Bootstrapping & Safety")
    try:
        create_restore_point()
    except LilBroError as e:
        print_error(str(e))
        if not prompt_approval("Restore point creation failed. Continue anyway?"):
            return

    # -- Phase 2: Deep System Scan --
    print_header("Phase 2: Deep System Scan")

    lhm_available = lhm.start()
    if lhm_available:
        print_success("Thermal monitoring active on port 8085.")
    else:
        print_info("Continuing without thermal monitoring -- Cinebench will still run.")

    dump_path = dump_system_specs()
    if dump_path:
        print_info(f"Full system specs saved to {dump_path}")
        try:
            with open(dump_path, "r", encoding="utf-8") as f:
                specs_preview = json.load(f)
            hw = extract_hardware_summary(specs_preview)
            print()
            print_key_value("CPU", hw.get('cpu', 'Unknown'))
            print_key_value("GPU", hw.get('gpu', 'Unknown'))
            print_key_value("Driver", hw.get('gpu_driver', 'Unknown'))
            print_key_value("RAM", f"{hw.get('ram_gb', 0)} GB @ {hw.get('ram_mhz', 0)} MHz")
            print_key_value("OS", hw.get('os', 'Unknown'))
        except Exception:
            pass

    # -- Phase 3: Baseline Benchmark --
    print_header("Phase 3: Baseline Benchmark")

    runner = BenchmarkRunner()
    benchmark_skipped = thermal_safety_gate(lhm_available)

    baseline: dict = {"status": "skipped", "message": "Skipped due to high idle temps"}
    peak_temps: dict[str, float] = {}

    if not benchmark_skipped:
        if lhm_available:
            thermal.start()
            print_info("Thermal monitoring active -- sampling temperatures during benchmark.")

        baseline = runner.run_benchmark(full_suite=False)

        if baseline.get("status") == "success":
            print_success("Baseline Benchmark Complete!")
            print_info(f"Scores: {baseline.get('scores', {})}")

        if lhm_available:
            thermal.stop()
            peak_temps = thermal.get_peak_temps()
            if peak_temps:
                cpu_peak = thermal.get_cpu_peak()
                gpu_peak = thermal.get_gpu_peak()
                parts = []
                if cpu_peak is not None:
                    parts.append(f"CPU: {cpu_peak:.1f}\u00b0C")
                if gpu_peak is not None:
                    parts.append(f"GPU: {gpu_peak:.1f}\u00b0C")
                if parts:
                    print_info(
                        f"Peak temps during benchmark: {', '.join(parts)} "
                        f"({thermal.sample_count} samples)"
                    )
            else:
                print_warning("Thermal monitor ran but captured no temperature data.")

    # -- Phase 4: Apply Esports Configurations --
    print_header("Phase 4: Apply Esports Configurations")

    specs: dict = {}
    if dump_path:
        try:
            with open(dump_path, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception as e:
            print_warning(f"Could not load specs file: {e}")

    if not specs:
        print_warning("No system data available -- skipping configuration checks.")
    else:
        findings = [
            analyze_display(specs),
            analyze_game_mode(specs),
            analyze_power_plan(specs),
            analyze_xmp(specs),
            analyze_rebar(specs),
            analyze_temp_folders(specs),
        ]

        thermal_finding = analyze_thermals(
            peak_temps,
            cpu_peak=thermal.get_cpu_peak() if lhm_available else None,
            gpu_peak=thermal.get_gpu_peak() if lhm_available else None,
        )
        findings.append(thermal_finding)

        print()
        print_accent("Alright, wiggle your mouse for 3 seconds -- we'll measure the polling rate.")
        print_prompt("Press Enter when you're ready... ")
        input()
        mouse_result = check_polling_rate()
        if mouse_result.get("status") == "WARNING":
            findings.append({
                "check": "mouse_polling",
                "status": "WARNING",
                "current_hz": mouse_result.get("current_hz", 0),
                "message": mouse_result.get("message", ""),
                "can_auto_fix": False,
            })

        print()
        warnings = [f for f in findings if f["status"] == "WARNING"]
        oks      = [f for f in findings if f["status"] == "OK"]
        unknowns = [f for f in findings if f["status"] not in ("OK", "WARNING")]
        print_audit_summary(len(oks), len(warnings), len(unknowns))
        print()
        for finding in findings:
            print_finding(finding["check"], finding["message"], finding["status"])

        print()
        hardware = extract_hardware_summary(specs)
        llm = get_llm()
        if llm is not None:
            print_dim("Generating AI-powered recommendations...")
        else:
            print_dim("Generating recommendations...")
        proposals = propose_actions(hardware, findings, llm)

        run_approval_flow(proposals, specs)

    # -- Phase 5: Final Verification Benchmark --
    print_header("Phase 5: Final Verification Benchmark")

    final_skipped = thermal_safety_gate(
        lhm_available,
        skip_message="Skipping final benchmark.",
        approval_prompt="Temperatures are elevated. Run the final benchmark anyway?",
    )

    if not final_skipped:
        if lhm_available:
            thermal.start()

        final = runner.run_benchmark(full_suite=True)

        if lhm_available:
            thermal.stop()

        if final.get("status") == "success":
            print_success("Final Benchmark Complete!")
            print_info(f"After:  {final.get('scores', {})}")
            print_info(f"Before: {baseline.get('scores', {})}")
    else:
        print_info("Final benchmark was skipped -- no comparison available.")

    print_header("Optimization Pipeline Complete")
```

---

### Step 7: Create `src/pipeline/menu.py`

Moves `menu_loop()` and `setup_ai_model()` from main.py (lines 57-129). Replaces `global _llm` with `get_llm()`/`set_llm()`.

```python
"""Main menu loop and AI model setup."""

import sys
from colorama import Fore, Style

from src.llm.model_loader import load_model, get_model_status
from src.utils.formatting import (
    print_header, print_info, print_warning, print_error,
    print_success, print_key_value, print_prompt,
)
from src.pipeline._state import get_llm, set_llm
from src.pipeline.phases import run_optimization_pipeline


def menu_loop():
    """3-option main menu: Pipeline, AI Setup, Exit."""
    while True:
        print_header("Main Menu")

        if get_llm() is not None:
            print_key_value("AI Model", "ready", value_color=Fore.GREEN)
        else:
            print_key_value("AI Model", "not loaded", value_color=Fore.YELLOW)

        print(f"  {Fore.CYAN}1.{Style.RESET_ALL} Run Full Esports Optimization Pipeline")
        print(f"  {Fore.CYAN}2.{Style.RESET_ALL} Setup AI Model")
        print(f"  {Fore.CYAN}3.{Style.RESET_ALL} Exit")

        print()
        print_prompt("Select an option [1-3]: ")
        choice = input().strip()

        if choice == '1':
            run_optimization_pipeline()
        elif choice == '2':
            setup_ai_model()
        elif choice == '3':
            print_info("shutting down, stay sweaty lil_bro.")
            sys.exit(0)
        else:
            print_error("Invalid choice. Try again.")


def setup_ai_model():
    """Interactive AI model management -- shows status, offers download, loads model."""
    print_header("AI Model Setup")

    status = get_model_status()

    if status["llama_installed"]:
        print_success("llama-cpp-python installed")
    else:
        print_warning("llama-cpp-python is not installed")
        print_info("Install with:  uv pip install llama-cpp-python")
        print_info(
            "\nThe optimization pipeline works without it -- "
            "you'll get standard recommendations instead of AI-generated ones.\n"
        )
        return

    if status["model_downloaded"]:
        print_success(f"Model downloaded: {status['model_path']}")
    else:
        print_info("Model not yet downloaded")
        print_info(f"Expected path: {status['model_path']}")

    if get_llm() is not None:
        print_success("Model loaded and ready")
        print_info("\nNothing to do -- AI model is already set up.")
        return

    print()
    result = load_model()
    set_llm(result)

    if get_llm() is not None:
        print_success("\nAI model is ready. The pipeline will use AI-powered explanations.")
    else:
        print_info(
            "\nThe pipeline works without the AI model -- "
            "you'll get standard recommendations."
        )
```

---

### Step 8: Rewrite `src/main.py`

Replace the entire 549-line file with this ~48-line thin entry point:

```python
"""
lil_bro -- Entry point.

Thin wrapper that handles:
  - multiprocessing freeze_support (PyInstaller)
  - File integrity verification (frozen builds)
  - Admin privilege check
  - Delegates to pipeline.menu for the main loop
"""

import multiprocessing
import sys

from src.utils.formatting import print_info, print_warning, print_error, print_accent
from src.utils.errors import AdminRequiredError
from src.bootstrapper import check_admin
from src.pipeline.banner import print_banner
from src.pipeline.menu import menu_loop


def main():
    multiprocessing.freeze_support()
    try:
        from src.utils.integrity import verify_integrity
        verify_integrity()

        print_banner()

        print_info("Checking system privileges...")
        try:
            check_admin()
        except AdminRequiredError as e:
            print_error(str(e))
            print_warning("Some features (like Restore Point Creation) will fail without Admin rights.")
            print()

        menu_loop()

    except KeyboardInterrupt:
        print_accent("\nCtrl+C detected. Exiting...")
        sys.exit(0)
    except Exception as e:
        print_error(f"Fatal unhandled exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

### Step 9: Create Test Files

#### `tests/test_parse_selection.py` (12 tests)

```python
"""Tests for src.pipeline.approval.parse_selection."""
import pytest
from src.pipeline.approval import parse_selection


class TestParseSelection:
    def test_empty_string_returns_empty_list(self):
        assert parse_selection("", 5) == []

    def test_skip_returns_empty_list(self):
        assert parse_selection("skip", 5) == []

    def test_s_returns_empty_list(self):
        assert parse_selection("s", 5) == []

    def test_all_returns_full_range(self):
        assert parse_selection("all", 3) == [1, 2, 3]

    def test_single_number(self):
        assert parse_selection("2", 5) == [2]

    def test_multiple_numbers(self):
        assert parse_selection("1 3", 5) == [1, 3]

    def test_out_of_range_returns_none(self):
        assert parse_selection("6", 5) is None

    def test_zero_returns_none(self):
        assert parse_selection("0", 5) is None

    def test_negative_returns_none(self):
        assert parse_selection("-1", 5) is None

    def test_non_numeric_returns_none(self):
        assert parse_selection("abc", 5) is None

    def test_whitespace_handling(self):
        assert parse_selection("  1  3  ", 5) == [1, 3]

    def test_case_insensitive_all(self):
        assert parse_selection("ALL", 3) == [1, 2, 3]
```

#### `tests/test_thermal_gate.py` (6 tests)

```python
"""Tests for src.pipeline.thermal_gate.thermal_safety_gate."""
from unittest.mock import patch
from src.pipeline.thermal_gate import thermal_safety_gate


class TestThermalSafetyGate:
    def test_no_lhm_returns_false(self):
        """No LHM available -- should not skip."""
        assert thermal_safety_gate(lhm_available=False) is False

    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    def test_safe_temps_returns_false(self, mock_check, mock_fetch):
        """Safe temps -- proceed."""
        mock_fetch.return_value = {"cpu": 45.0}
        mock_check.return_value = {"safe": True, "message": "Temps look good."}
        assert thermal_safety_gate(lhm_available=True) is False

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=True)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    def test_elevated_user_approves_returns_false(self, mock_check, mock_fetch, mock_approval):
        """Elevated temps but user approves -- proceed."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "CPU hot!"}
        assert thermal_safety_gate(lhm_available=True) is False

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=False)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    def test_elevated_user_declines_returns_true(self, mock_check, mock_fetch, mock_approval):
        """Elevated temps and user declines -- skip."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "CPU hot!"}
        assert thermal_safety_gate(lhm_available=True) is True

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=False)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    def test_custom_skip_message(self, mock_check, mock_fetch, mock_approval, capsys):
        """Custom skip message is printed."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "hot"}
        thermal_safety_gate(lhm_available=True, skip_message="Custom skip msg")
        out = capsys.readouterr().out
        assert "Custom skip msg" in out

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=False)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    def test_custom_approval_prompt(self, mock_check, mock_fetch, mock_approval):
        """Custom approval prompt is passed to prompt_approval."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "hot"}
        thermal_safety_gate(lhm_available=True, approval_prompt="Custom prompt?")
        mock_approval.assert_called_once_with("Custom prompt?")
```

#### `tests/test_fix_dispatch.py` (10 tests)

```python
"""Tests for src.pipeline.fix_dispatch -- dispatch registry + handlers."""
from unittest.mock import patch, MagicMock
from src.pipeline.fix_dispatch import FIX_REGISTRY, execute_fix


class TestFixRegistry:
    def test_all_expected_checks_registered(self):
        """All 4 auto-fixable checks must be in the registry."""
        expected = {"display", "power_plan", "temp_folders", "game_mode"}
        assert set(FIX_REGISTRY.keys()) == expected

    def test_all_handlers_are_callable(self):
        for name, handler in FIX_REGISTRY.items():
            assert callable(handler), f"{name} handler is not callable"

    def test_unknown_check_returns_false(self):
        assert execute_fix("nonexistent_check", {}) is False


class TestFixGameMode:
    @patch("src.agent_tools.game_mode.set_game_mode")
    def test_game_mode_success(self, mock_set):
        assert execute_fix("game_mode", {}) is True
        mock_set.assert_called_once_with(enabled=True)

    @patch("src.agent_tools.game_mode.set_game_mode", side_effect=Exception("denied"))
    def test_game_mode_failure(self, mock_set):
        assert execute_fix("game_mode", {}) is False


class TestFixTempFolders:
    @patch("src.agent_tools.temp_audit.clean_temp_folders")
    def test_temp_cleanup_success(self, mock_clean):
        specs = {"TempFolders": {"details": {"/tmp": 1000}}}
        assert execute_fix("temp_folders", specs) is True
        mock_clean.assert_called_once_with({"/tmp": 1000})

    @patch("src.agent_tools.temp_audit.clean_temp_folders")
    def test_temp_cleanup_empty_specs(self, mock_clean):
        assert execute_fix("temp_folders", {}) is True
        mock_clean.assert_called_once_with({})


class TestFixDisplay:
    @patch("src.agent_tools.display_setter.apply_display_mode")
    @patch("src.agent_tools.display_setter.find_best_mode")
    @patch("src.collectors.sub.monitor_dumper.get_all_displays", return_value=["\\\\.\\DISPLAY1"])
    def test_display_success(self, mock_displays, mock_find, mock_apply):
        mock_mode = MagicMock()
        mock_mode.dmDisplayFrequency = 144
        mock_mode.dmPelsWidth = 1920
        mock_mode.dmPelsHeight = 1080
        mock_find.return_value = mock_mode
        mock_apply.side_effect = [(True, "Validated"), (True, "Applied")]
        assert execute_fix("display", {}) is True

    @patch("src.agent_tools.display_setter.find_best_mode", return_value=None)
    @patch("src.collectors.sub.monitor_dumper.get_all_displays", return_value=[])
    def test_display_no_mode_found(self, mock_displays, mock_find):
        assert execute_fix("display", {}) is False
```

**Important patching note:** Because fix handlers use lazy imports (`from src.agent_tools.game_mode import set_game_mode` inside the function body), the patch target must be the *original module*, not `src.pipeline.fix_dispatch`. For example: `@patch("src.agent_tools.game_mode.set_game_mode")`, not `@patch("src.pipeline.fix_dispatch.set_game_mode")`.

---

### Step 10: Full Verification

Run these checks in order:

**1. Import smoke test** (no circular imports):
```bash
python -c "from src.pipeline._state import get_llm, set_llm"
python -c "from src.pipeline.banner import print_banner"
python -c "from src.pipeline.thermal_gate import thermal_safety_gate"
python -c "from src.pipeline.fix_dispatch import FIX_REGISTRY, execute_fix"
python -c "from src.pipeline.approval import parse_selection, run_approval_flow"
python -c "from src.pipeline.phases import run_optimization_pipeline"
python -c "from src.pipeline.menu import menu_loop"
python -c "from src.main import main"
```

**2. Full test suite:**
```bash
python -m pytest tests/ -v
```
All 215 existing + ~28 new tests must pass.

**3. Line count check:**
```bash
wc -l src/main.py
```
Should be ~48 lines.

**4. Manual smoke test:** Run `python -m src.main` and verify:
- Banner prints correctly
- Menu shows 3 options with AI Model status
- Option 2 (AI Setup) shows status
- Option 3 exits with "stay sweaty lil_bro"
- Option 1 starts the pipeline (Ctrl+C to exit)

**5. PyInstaller build** (optional):
```bash
python build.py --clean
```

---

## Gotchas

### Circular Import Prevention
The `_state.py` module imports nothing from `src/` — it's the firewall. The import graph has no cycles:
```
main -> banner, menu -> phases -> approval -> fix_dispatch
                                -> thermal_gate
                                -> _state
                     -> _state
```

### `_llm` Getter/Setter Rationale
Never write `from src.pipeline._state import _llm`. That creates a local Python name binding that never sees updates when `set_llm()` is called. The getter/setter pattern forces you through the module-level variable.

### PyInstaller Auto-Discovery
PyInstaller traces imports from `src/main.py`. Since main.py imports `pipeline.menu`, which imports `pipeline.phases`, the full dependency chain is discovered automatically. No changes to `lil_bro.spec` or `build.py` needed. The `pyproject.toml` package finder (`include = ["src*"]`) also auto-discovers `src/pipeline/`.

### Lazy Imports in Fix Handlers
Each handler in `fix_dispatch.py` uses lazy imports inside the function body (e.g., `from src.agent_tools.game_mode import set_game_mode`). This means:
- Patch targets must use the original module path, not `src.pipeline.fix_dispatch`
- If testing is too painful, move imports to the top of `fix_dispatch.py` — startup cost is negligible since this module is only imported when the pipeline runs

### CLAUDE.md Architecture Update
After completing the refactor, update the Architecture section in `CLAUDE.md` to include:
```
  pipeline/
    __init__.py          -- Package marker
    _state.py            -- Shared _llm state (get_llm/set_llm)
    banner.py            -- ASCII art banner
    menu.py              -- 3-option menu loop + AI model setup
    approval.py          -- Proposal display, selection parsing, fix execution
    fix_dispatch.py      -- Check->fix dispatch registry
    thermal_gate.py      -- Pre-benchmark thermal safety check
    phases.py            -- 5-phase pipeline orchestrator
```

Also update the main.py description from "5-phase pipeline orchestrator + 3-option menu" to "Thin entry point (integrity, admin, banner, menu)".
