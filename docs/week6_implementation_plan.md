# Week 5 Implementation Plan

**Written:** 2026-03-23
**Status:** Ready to implement
**Depends on:** Terminal UI redesign (`docs/terminal_ui_redesign.md`) should land first

---

## Overview

| Task | What | Effort |
|------|------|--------|
| B1 | Game Mode auto-fix via registry | ~15 min |
| B2 | Thermal fallback template + brand voice idle warning | ~15 min |
| B3 | Extra tests for 4 thin modules | ~20 min |
| B4 | Action logger progress bar with animation in terminal | ~30 min |
| C1 | NVIDIA driver version display in pipeline output | ~10 min |

---

## B1: Game Mode Auto-Fix

### Gap
`game_mode.py` already reads `HKCU\SOFTWARE\Microsoft\GameBar\AutoGameModeEnabled` via `get_game_mode_status()`. But `analyze_game_mode()` returns `can_auto_fix: False` and tells the user to go toggle it manually in Windows Settings. This is a simple registry write — lil_bro should just do it.

### Changes

#### `src/agent_tools/game_mode.py`

**Add `set_game_mode()` function** after `get_game_mode_status()`:

```python
def set_game_mode(enabled: bool) -> bool:
    """
    Sets Windows Game Mode on/off by writing AutoGameModeEnabled.

    Args:
        enabled: True to enable Game Mode, False to disable.

    Returns:
        True if the write succeeded.

    Raises:
        ScannerError: If the registry write fails.
    """
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\GameBar",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "AutoGameModeEnabled", 0, winreg.REG_DWORD, 1 if enabled else 0)
        return True
    except Exception as e:
        raise ScannerError(f"Failed to set Game Mode: {e}")
```

**Modify `analyze_game_mode()`** — change `can_auto_fix: False` to `can_auto_fix: True` in the WARNING return (line 21):

```python
# Before
"can_auto_fix": False,

# After
"can_auto_fix": True,
```

Also update the message to drop the manual instructions:

```python
# Before
"message": "Windows Game Mode is DISABLED. Enable via Settings > Gaming > Game Mode.",

# After
"message": "Windows Game Mode is DISABLED — lil_bro can flip this on for you.",
```

#### `src/main.py` — `_execute_fix()`

Add `game_mode` case (after the `temp_folders` case, around line 247):

```python
elif check == "game_mode":
    from src.agent_tools.game_mode import set_game_mode
    try:
        set_game_mode(enabled=True)
        print_success("[game_mode] Game Mode enabled.")
        return True
    except Exception as e:
        print_error(f"[game_mode] Failed: {e}")
        return False
```

#### `src/llm/action_proposer.py` — `_FALLBACK`

Update the `game_mode` template:

```python
"game_mode": {
    "finding": "game_mode",
    "severity": "MEDIUM",
    "explanation": (
        "Windows Game Mode is off. It prioritizes CPU/GPU resources to the active "
        "game and reduces background jitter."
    ),
    "proposed_action": "Enable Game Mode via registry",
    "can_auto_fix": True,  # was False
},
```

#### Tests — `tests/test_game_mode.py`

Add 3 tests:

1. `test_set_game_mode_enable()` — Mock `winreg.CreateKeyEx` + `SetValueEx`, call `set_game_mode(True)`, assert `SetValueEx` called with `(key, "AutoGameModeEnabled", 0, REG_DWORD, 1)`
2. `test_set_game_mode_disable()` — Same but `enabled=False`, assert value is `0`
3. `test_set_game_mode_failure()` — Mock `CreateKeyEx` raising `PermissionError`, assert `ScannerError` is raised
4. `test_analyze_game_mode_can_auto_fix()` — Call `analyze_game_mode({"GameMode": {"enabled": False}})`, assert `can_auto_fix is True`

### Verification
- `python -m pytest tests/test_game_mode.py -v` — all tests pass
- Existing tests still pass (the `analyze_game_mode` tests mock the specs dict, not the registry)

---

## B2: Thermal Fallback Template + Brand Voice Idle Warning

### Gap 1: Missing fallback template
`action_proposer.py` has static fallback templates for all 7 checks but NOT for `thermals`. If the LLM is unavailable and thermals are bad, no proposal is generated.

### Gap 2: No brand-voice idle temp warning
`check_idle_thermals()` gives clinical messages. At launch, if the PC is already cooking (>80C), the user should get a loud, on-brand warning.

### Changes

#### `src/llm/action_proposer.py`

**Add `thermals` to `build_llm_input()`** (new `elif` in the check mapping, around line 65):

```python
elif check == "thermals":
    entry.update({
        "cpu_peak": f.get("cpu_peak"),
        "gpu_peak": f.get("gpu_peak"),
    })
```

**Add `thermals` to `_FALLBACK`** dict:

```python
"thermals": {
    "finding": "thermals",
    "severity": "HIGH",
    "explanation": (
        "Your temps are running hot under load — your CPU or GPU is at risk of "
        "thermal throttling, which silently kills your FPS. Clean your fans, "
        "check your thermal paste, and make sure your case has decent airflow."
    ),
    "proposed_action": "Improve cooling: clean dust filters, check thermal paste, optimize case airflow (manual)",
    "can_auto_fix": False,
},
```

#### `src/agent_tools/thermal_guidance.py` — Brand voice idle warning

**Update `check_idle_thermals()`** — when temps >= 80C, use the brand voice. Replace the `warnings` message building (lines 192-208) with:

```python
if cpu_temp is not None and cpu_temp >= CPU_IDLE_WARN:
    if cpu_temp >= 80.0:
        warnings.append(
            f"CPU is at {cpu_temp:.0f}°C AT IDLE — clean yo fans or repaste "
            f"your CPU, your PC is dying yo. Under load this thing will hit "
            f"{cpu_temp + 15:.0f}°C+ and throttle hard."
        )
    else:
        warnings.append(
            f"CPU is already at {cpu_temp:.0f}°C at idle — "
            f"under full load it could exceed {cpu_temp + 15:.0f}°C."
        )

if gpu_temp is not None and gpu_temp >= GPU_IDLE_WARN:
    if gpu_temp >= 80.0:
        warnings.append(
            f"GPU is at {gpu_temp:.0f}°C AT IDLE — that's cooked. "
            f"Check your GPU fans are actually spinning, clean the dust out, "
            f"and make sure your case isn't suffocating it. Under load "
            f"you're looking at {gpu_temp + 15:.0f}°C+ easy."
        )
    else:
        warnings.append(
            f"GPU is already at {gpu_temp:.0f}°C at idle — "
            f"under full load it could exceed {gpu_temp + 15:.0f}°C."
        )
```

The >= 80C messages use casual brand voice. The 75-79C range keeps the existing clinical tone since it's warm but not alarming.

#### Tests — `tests/test_thermal_guidance.py`

Add 2 tests:

1. `test_idle_cpu_extreme_heat_brand_voice()` — Call `check_idle_thermals({"cpu/package": 85.0})`, assert `"clean yo fans"` in message and `safe is False`
2. `test_idle_gpu_extreme_heat_brand_voice()` — Call `check_idle_thermals({"gpu/core": 82.0})`, assert `"that's cooked"` in message and `safe is False`

### Verification
- `python -m pytest tests/test_thermal_guidance.py tests/test_action_proposer.py -v`

---

## B3: Test Coverage Expansion

### Target: 4 modules with 3-4 tests each

#### `tests/test_display.py` — Add 4 tests

Current: 4 tests covering OK/WARNING/ERROR states for refresh rate.

Add:

1. `test_analyze_display_ok()` — Feed specs with matching current/max refresh rate, assert `status == "OK"`
2. `test_analyze_display_warning_mismatch()` — Feed specs with 60Hz current, 144Hz max, assert `status == "WARNING"`, `can_auto_fix == True`
3. `test_analyze_display_missing_capabilities()` — Feed specs with empty `DisplayCapabilities`, assert graceful handling (UNKNOWN or OK with message)
4. `test_analyze_display_multi_monitor()` — Feed specs with 2 monitors (one OK, one WARNING), assert the finding reflects the worst case

Note: These test the `analyze_display()` pure analyzer (from specs dict), not the WMI-dependent `check_refresh_rate()`.

#### `tests/test_spec_dumper.py` — Add 4 tests

Current: 3 tests covering nvidia-smi success/not-found/error.

Add:

1. `test_get_nvidia_smi_multi_gpu()` — Mock XML with 2 `<gpu>` elements, assert both are returned with correct fields
2. `test_get_nvidia_smi_missing_fields()` — Mock XML where `bar1_memory_usage/used` and `pci` elements are missing, assert graceful defaults (0, None)
3. `test_dump_system_specs_partial_failure()` — Mock one collector (`get_nvidia_smi`) raising `FileNotFoundError`, verify the dump still completes with other collectors populated and NVIDIA key contains the error
4. `test_dump_system_specs_writes_json()` — Mock all collectors, call `dump_system_specs(tmp_path)`, verify JSON file is written and loadable

#### `tests/test_temp_audit.py` — Add 4 tests

Current: 4 tests covering size formatting, scan, and clean.

Add:

1. `test_clean_temp_folders_permission_error()` — Mock `os.remove` raising `PermissionError` for one file, assert it continues cleaning others and reports partial success
2. `test_clean_temp_folders_locked_file()` — Mock `os.remove` raising `OSError` (file in use), assert skip + continue
3. `test_scan_temp_folders_empty_dirs()` — Mock `scan_dir_size` returning `(0, 0)` for all targets, assert total is 0 bytes, 0 files
4. `test_analyze_temp_folders_under_threshold()` — Feed specs with `TempFolders.total_bytes` under 1GB, assert `status == "OK"`

#### `tests/test_mouse.py` — Add 3 tests

Current: 3 tests covering optimal/acceptable/warning polling rates.

Add:

1. `test_check_polling_rate_zero_samples()` — Mock `_fallback_measure_rate` returning 0, assert graceful handling (ERROR or UNKNOWN status, not a crash)
2. `test_check_polling_rate_very_high()` — Mock returning 8000 Hz (8kHz mouse), assert `status == "OK"`
3. `test_check_polling_rate_error()` — Mock `_fallback_measure_rate` raising an exception, assert status is "ERROR" with a message

### Verification
- `python -m pytest tests/test_display.py tests/test_spec_dumper.py tests/test_temp_audit.py tests/test_mouse.py -v`
- Then full suite: `python -m pytest tests/ -v`

---

## B4: Action Logger Progress Bar with Animation

### Goal
During fix execution in Phase 4, show a terminal progress bar with a traveling animation (not a boring static bar). The bar should:
- Show which fix is currently running
- Animate a graphic traveling left to right
- Show completion percentage
- Look awesome in the terminal

### Design

#### `src/utils/progress_bar.py` (new file)

A self-contained animated progress bar using ANSI escape codes + threading.

```python
class AnimatedProgressBar:
    """
    Terminal progress bar with a traveling glow animation.

    Usage:
        bar = AnimatedProgressBar(total=3, label="Applying fixes")
        bar.start()
        bar.update(1, "Setting refresh rate...")
        bar.update(2, "Switching power plan...")
        bar.update(3, "Cleaning temp files...")
        bar.finish()
    """
```

**Animation style — "plasma sweep":**
- Bar width: 30 chars
- Filled portion uses bright colored blocks: `█`
- A 3-char "glow" segment (`▓▒░`) sweeps across the filled portion continuously
- Unfilled portion: dim `░`
- Colors: `Fore.CYAN` for filled, `Fore.MAGENTA` for the glow sweep, `Style.DIM` for unfilled

**Example frames:**
```
  ⚡ Applying fixes...
  [▒░███████████░░░░░░░░░░░░░░░░░] 33%  Setting refresh rate...
  [███████▒░████░░░░░░░░░░░░░░░░░] 33%  Setting refresh rate...
  [█████████████▒░░░░░░░░░░░░░░░░] 33%  Setting refresh rate...
```

**Implementation:**
- Uses a background `threading.Thread` for animation (redraws at ~10 FPS)
- `update(step, message)` advances the bar and changes the status message
- `finish()` stops the animation thread, prints final state
- Uses `\r` + `sys.stdout.write` for in-place updates (single line, no scroll)
- Respects `colorama.init(autoreset=True)` — all ANSI codes are self-contained

#### `src/main.py` — `_run_approval_flow()`

After collecting the user's batch selection and before executing fixes, start the progress bar:

```python
from src.utils.progress_bar import AnimatedProgressBar

# In the fix execution loop (around line 302):
bar = AnimatedProgressBar(total=len(selected_proposals), label="Applying fixes")
bar.start()

for i, (_n, proposal) in enumerate(sorted(selected_proposals.items()), 1):
    check = proposal.get("finding", "")
    bar.update(i, f"Fixing {check.replace('_', ' ')}...")
    _execute_fix(check, specs)

bar.finish()
```

#### `src/utils/action_logger.py` — Console echo

Update `log_action()` to also print to stdout (dim, non-intrusive):

```python
def log_action(self, component: str, action: str, details: str = ""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{component}] {action}"
    if details:
        log_entry += f" | {details}"

    # Write to file
    try:
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"Failed to write to action log: {e}")

    # Echo to terminal (dim, below progress bar)
    from colorama import Style
    print(f"{Style.DIM}  {log_entry}{Style.RESET_ALL}")
```

#### Tests — `tests/test_progress_bar.py` (new file)

1. `test_progress_bar_update()` — Create bar with `total=3`, call `update(1)`, `update(2)`, `update(3)`, `finish()` — no crash
2. `test_progress_bar_finish_cleans_up()` — Start bar, finish it, assert the animation thread is no longer alive
3. `test_progress_bar_zero_total()` — `AnimatedProgressBar(total=0)` — should not divide by zero

### Verification
- `python -m pytest tests/test_progress_bar.py -v`
- Visual spot-check in terminal

---

## C1: NVIDIA Driver Version Display

### Gap
`nvidia_smi_dumper.py` already collects the driver version and stores it in `full_specs.json` under `NVIDIA[0].Driver`. `dump_parser.py` already extracts it as `hardware["gpu_driver"]`. It's just never shown to the user.

### Changes

#### `src/main.py` — Phase 2 output (after spec dump, around line 346)

After the `print_info(f"Full system specs saved to {dump_path}")` line, add a hardware summary display:

```python
if dump_path:
    print_info(f"Full system specs saved to {dump_path}")

    # Show key hardware info to the user
    try:
        with open(dump_path, "r", encoding="utf-8") as f:
            specs_preview = json.load(f)
        hw = extract_hardware_summary(specs_preview)

        print()
        print_info(f"CPU:    {hw.get('cpu', 'Unknown')}")
        print_info(f"GPU:    {hw.get('gpu', 'Unknown')}")
        print_info(f"Driver: {hw.get('gpu_driver', 'Unknown')}")
        print_info(f"RAM:    {hw.get('ram_gb', 0)} GB @ {hw.get('ram_mhz', 0)} MHz")
        print_info(f"OS:     {hw.get('os', 'Unknown')}")
    except Exception:
        pass  # Non-critical — don't block pipeline over a display error
```

This reuses `extract_hardware_summary()` which is already imported. No new API calls, no network. Just extracting what's already collected and showing it.

**Note:** The terminal UI redesign (`docs/terminal_ui_redesign.md`) should apply styling to these lines when it lands — using `print_dim` for labels and `print_accent` for values. For now, `print_info` is fine.

### NVIDIA-only scope
- AMD driver version: deferred (no AMD GPU to test)
- Intel driver version: deferred (not the target user)
- The `dump_parser.py` fallback to WMI `VideoController` doesn't include driver version — that's fine for now since we're NVIDIA-focused

### Tests
No new tests needed — `extract_hardware_summary` is already tested via `test_action_proposer.py` (it uses the same data path). The display is pure UI output.

### Verification
- Run pipeline, verify GPU driver version appears in Phase 2 output
- Verify against `nvidia-smi` output directly

---

## Implementation Order

1. **C1** — Driver version display (~10 min, zero risk, instant gratification)
2. **B1** — Game Mode auto-fix (~15 min, small scope, adds real auto-fix capability)
3. **B2** — Thermal fallback + brand voice (~15 min, fills a gap + adds personality)
4. **B3** — Test expansion (~20 min, hardens everything above)
5. **B4** — Progress bar animation (~30 min, biggest scope, most creative freedom)

Run `python -m pytest tests/ -v` after each step.

---

## Files Modified Summary

| File | B1 | B2 | B3 | B4 | C1 |
|------|----|----|----|----|-----|
| `src/agent_tools/game_mode.py` | add `set_game_mode()`, change `can_auto_fix` | | | | |
| `src/agent_tools/thermal_guidance.py` | | brand voice messages | | | |
| `src/llm/action_proposer.py` | update fallback `can_auto_fix` | add `thermals` template + LLM input | | | |
| `src/main.py` | add `game_mode` to `_execute_fix` | | | integrate progress bar | add hardware summary display |
| `src/utils/action_logger.py` | | | | add console echo | |
| `src/utils/progress_bar.py` (new) | | | | animated progress bar class | |
| `tests/test_game_mode.py` | +4 tests | | | | |
| `tests/test_thermal_guidance.py` | | +2 tests | | | |
| `tests/test_display.py` | | | +4 tests | | |
| `tests/test_spec_dumper.py` | | | +4 tests | | |
| `tests/test_temp_audit.py` | | | +4 tests | | |
| `tests/test_mouse.py` | | | +3 tests | | |
| `tests/test_progress_bar.py` (new) | | | | +3 tests | |
