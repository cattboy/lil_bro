# Week 1 PoC Implementation Walkthrough

The "Week 1 Proof of Concept" for `lil_bro` is fully implemented and ready for local testing.

## Summary of Changes

1. **Project Scaffolding**
   - Created full Python project layout (`src/` and `tests/`)
   - Configured [pyproject.toml](file:///c:/1_Coding/1_lil_bro/pyproject.toml) with necessary dependencies (`wmi`, `psutil`, `colorama`)
   - Implemented a unified set of formatting helpers and a custom error hierarchy

2. **Core Modules Implemented**
   - [bootstrapper.py](file:///c:/1_Coding/1_lil_bro/src/bootstrapper.py): Manages UAC privilege elevation checks and triggers PowerShell to cleanly create a System Restore Point. Features strict human-in-the-loop approval.
   - [scanners/display.py](file:///c:/1_Coding/1_lil_bro/src/scanners/display.py): Submits WMI queries to fetch the active monitor refresh rate and intelligently flags user bottlenecks (e.g., getting stuck at 60Hz).
   - [scanners/mouse.py](file:///c:/1_Coding/1_lil_bro/src/scanners/mouse.py): Uses native CTypes to hit Win32 APIs (GetCursorPos), evaluating mouse input density to ensure gamers aren't trapped at severe 125Hz polling rates.
   - [scanners/temp_audit.py](file:///c:/1_Coding/1_lil_bro/src/scanners/temp_audit.py): Quickly traverses `os.walk` across three critical system bloat directories (`TEMP`, `WinTemp`, `SoftwareDistribution`), tracking accumulated garbage volume.

3. **Interactive CLI ([main.py](file:///c:/1_Coding/1_lil_bro/src/main.py))**
   - Presents a styled terminal menu displaying two major paths ("Configuration Check" and "Speed Up My PC").
   - Orchestrates the scanners and groups them securely.
   - Enforces the absolute rule that *no system change occurs without explicit terminal confirmation via [y/N] prompts*.

4. **Testing Suite**
   - Created a full set of `pytest` mock unit tests in the `tests/` directory ensuring the logic operates correctly completely offline without needing a real hardware environment.

## How to Test and Run Locally

1. Open an Administrator PowerShell or Command Prompt
2. Navigate to `c:\1_Coding\1_lil_bro`
3. Run the CLI tool:
   ```bash
   python -m src.main
   ```
4. *Recommendation:* Choose Option 1 ("Configuration Check") first to see read-only diagnostics on your display and mouse polling rates.

> [!TIP]
> If you test the Restore Point feature (Option 2), Windows typically restricts creating more than one restore point within a 24-hour window by default. If the command fails, it is usually because of this Windows policy, not the code.
