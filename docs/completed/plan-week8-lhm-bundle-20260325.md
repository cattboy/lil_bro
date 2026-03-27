# Plan: Bundle lhm-server.exe + Fix CPU Sensor Derivation

## Context

Implementing the approved design doc (2026-03-24): bundle a custom C# thermal sensor server (`lhm-server.exe`) using `LibreHardwareMonitorLib` so thermal monitoring works out of the box with zero user steps. Also appending two additional tasks before implementation begins:

- **Task 1 (PawnIO):** LHM recently upgraded from WinRing0 (ring-0 kernel driver, blocked by Windows) to PawnIO. The design doc's feasibility risk cites `WinRing0x64.sys` — that's outdated. We target latest LibreHardwareMonitorLib NuGet (post-PawnIO) and document the updated risk profile.
- **Task 2 (CPU sensor fix):** `_derive_cpu_temp` and `get_cpu_peak()` have a broken fallback: `max([v for k,v if "cpu" in k.lower()])` can return CPU Hotspot or CPU Core Max instead of CPU Package. AMD Ryzen's primary sensor (`"Core (Tctl/Tdie)"`) is entirely missed — returns None. Both need strict priority-ordered sensor selection before the thermal bundling work ships.

---

## Phase 1: Fix CPU Sensor Derivation (Task 2)

### 1a. `src/agent_tools/thermal_guidance.py`

**Rewrite `_derive_cpu_temp`** with priority-ordered, strict exclusion logic:

```python
_CPU_EXCLUDE_TERMS = ("hotspot", "hot spot", "vrm", "vr ", "core max", "max core")

def _derive_cpu_temp(temps: dict[str, float]) -> Optional[float]:
    """Extract the most representative CPU die temperature.

    Priority:
    1. CPU Package  — explicit package sensor (Intel + AMD)
    2. Tctl/Tdie    — AMD Ryzen die temperature (no "cpu" in LHM sensor name)
    3. CPU sensors  — any CPU sensor excluding hotspot/VRM/Core Max
    """
    # P1: CPU Package
    pkg = [v for k, v in temps.items()
           if "cpu" in k.lower() and "package" in k.lower()]
    if pkg:
        return max(pkg)

    # P2: AMD Tctl/Tdie
    tctl = [v for k, v in temps.items()
            if "tctl" in k.lower() or "tdie" in k.lower()]
    if tctl:
        return max(tctl)

    # P3: Generic CPU (excludes hotspot, VRM, Core Max)
    safe = [v for k, v in temps.items()
            if "cpu" in k.lower()
            and "gpu" not in k.lower()
            and not any(excl in k.lower() for excl in _CPU_EXCLUDE_TERMS)]
    return max(safe) if safe else None
```

**Fix inline fallback in `analyze_thermals()`** (lines 50-51) — replace the loose `"cpu"` filter with the same three-priority logic (or call `_derive_cpu_temp(peak_temps)` directly instead of duplicating). Use `_derive_cpu_temp` call.

### 1b. `src/benchmarks/thermal_monitor.py`

**Fix `get_cpu_peak()`** (lines 179-189) — same three-priority logic as above (copy the `_CPU_EXCLUDE_TERMS` constant or import from thermal_guidance if circular import is not a concern; otherwise inline). The current fallback at line 187-188 has the same `"any cpu"` problem.

### 1c. Tests

**`tests/test_thermal_guidance.py`** — add test cases:
- AMD Ryzen returns Tctl/Tdie value, not None
- CPU Hotspot is excluded from fallback
- CPU Core Max is excluded from fallback
- CPU VRM is excluded from fallback
- GPU Core sensor not matched by CPU derivation

**`tests/test_thermal_monitor.py`** — add equivalent `get_cpu_peak()` test cases.

---

## Phase 2: C# lhm-server.exe (Design Doc)

### 2a. New directory: `tools/lhm-server/`

**`LhmServer.csproj`:**
- Target: `.NET 8.0`
- Dependency: `LibreHardwareMonitorLib` NuGet — use **latest stable** (post-PawnIO, v0.9.3+, NOT pinned to pre-PawnIO v0.9.1)
- Output type: Console

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <AssemblyName>lhm-server</AssemblyName>
    <RootNamespace>LhmServer</RootNamespace>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="LibreHardwareMonitorLib" Version="0.9.*" />
  </ItemGroup>
</Project>
```

**`Program.cs`** (~120 lines):
- `Computer` with `IsCpuEnabled`, `IsGpuEnabled`, `IsMotherboardEnabled`
- Background thread: `hardware.Update()` every 1 second
- `HttpListener` on `http://localhost:8085/` → `/data.json`
- JSON output replicates LHM tree structure exactly: `Text`, `Children[]`, `Value` ("72.3 °C"), `RawValue` (float)
- Graceful shutdown on `Console.CancelKeyPress` and parent process exit (via stdin read or `Environment.Exit`)
- No GUI, no tray icon

**PawnIO note:** With LibreHardwareMonitorLib ≥0.9.3, the underlying driver is PawnIO (not WinRing0x64.sys). PawnIO is not ring-0; it does NOT extract `WinRing0x64.sys`. The design doc's feasibility risk about ring-0 driver extraction from nested temp paths is **resolved** — PawnIO handles driver lifecycle internally and does not require manual temp-path extraction. AV false positive risk is reduced but not eliminated (signed driver, not self-extracted).

**`build.ps1`:**
```powershell
$ErrorActionPreference = "Stop"
$OutDir = Join-Path $PSScriptRoot "dist"
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    Write-Error ".NET 8 SDK required."
    exit 1
}
dotnet publish -r win-x64 -c Release --self-contained `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:EnableCompressionInSingleFile=true `
    -o $OutDir
```

**`LICENSE-LHM.txt`** — MPL-2.0 license attribution for LibreHardwareMonitorLib.

**`reference-output.json`** — placeholder file noting it must be captured from a running LHM instance before structural diff testing. Can be populated post-build.

---

### 2b. `src/collectors/sub/lhm_sidecar.py`

**Three changes (per design doc):**

1. **Search paths** — add bundled lhm-server paths at top of `_LHM_SEARCH_PATHS`, before existing LHM install paths:
   - `sys._MEIPASS/tools/lhm-server.exe` (PyInstaller frozen)
   - `%APPDATA%\lil_bro\tools\lhm-server.exe` (first-run extraction fallback)
   - `<project_root>/tools/lhm-server/dist/lhm-server.exe` (dev/source tree)

2. **`find_lhm_executable()`** → change return type to `tuple[str | None, bool]`:
   - `bool` = `True` if it's `lhm-server.exe` (custom), `False` if it's the full LHM app

3. **`LHMSidecar.start()`** — use tuple return from `find_lhm_executable()`:
   - Custom server: launch as `[exe]` (no `--http-port` flag, port hardcoded)
   - Full LHM: launch as `[exe, "--http-port", str(LHM_PORT)]` (existing behavior)

   Also update `self._exe_path` path if it was set via `__init__` — preserve that override path.

---

### 2c. `build.py`

Add `build_lhm_server()` step before `run_pyinstaller()`:
- Runs `tools/lhm-server/build.ps1` via PowerShell
- On failure (no .NET SDK): print warning, continue build (graceful degradation)
- On success: verify `tools/lhm-server/dist/lhm-server.exe` exists

---

### 2d. `lil_bro.spec`

Add to `datas=[]`:
```python
datas=[
    ('tools/lhm-server/dist/lhm-server.exe', 'tools'),
    ('tools/lhm-server/LICENSE-LHM.txt', 'tools'),
],
```

Guard with `os.path.exists()` check so spec doesn't fail if lhm-server wasn't built.

---

## Phase 3: Tests for Python Changes

**`tests/test_lhm_sidecar.py`** — add test cases:
- `find_lhm_executable()` returns `(path, True)` when `lhm-server.exe` is found
- `find_lhm_executable()` returns `(path, False)` when full LHM is found
- `start()` launches custom server without `--http-port` arg
- `start()` launches full LHM with `--http-port` arg (existing behavior preserved)

---

## Phase 4: Docs + CLAUDE.md

- `CLAUDE.md`: add Week 8 roadmap entry
- Save this plan as `docs/plan-week8-lhm-bundle-20260325.md`

---

## File Change Summary

| File | Action | Notes |
|---|---|---|
| `src/agent_tools/thermal_guidance.py` | Modify | Fix `_derive_cpu_temp`, fix `analyze_thermals` inline fallback |
| `src/benchmarks/thermal_monitor.py` | Modify | Fix `get_cpu_peak()` fallback |
| `tests/test_thermal_guidance.py` | Modify | Add AMD Tdie, exclusion tests |
| `tests/test_thermal_monitor.py` | Modify | Add `get_cpu_peak()` exclusion tests |
| `src/collectors/sub/lhm_sidecar.py` | Modify | New search paths, tuple return, launch logic |
| `build.py` | Modify | Add `build_lhm_server()` step |
| `lil_bro.spec` | Modify | Add lhm-server.exe to datas |
| `tools/lhm-server/LhmServer.csproj` | Create | .NET 8 + LibreHardwareMonitorLib (latest) |
| `tools/lhm-server/Program.cs` | Create | HTTP sensor server ~120 lines |
| `tools/lhm-server/build.ps1` | Create | dotnet publish self-contained single-file |
| `tools/lhm-server/LICENSE-LHM.txt` | Create | MPL-2.0 attribution |
| `tools/lhm-server/reference-output.json` | Create | Placeholder; capture from running LHM |
| `CLAUDE.md` | Modify | Week 8 roadmap entry |

---

## Verification

1. **Task 2 tests:** `python -m pytest tests/test_thermal_guidance.py tests/test_thermal_monitor.py -v` — all new sensor exclusion tests pass
2. **Task 1 NuGet version:** `LhmServer.csproj` references `LibreHardwareMonitorLib` `0.9.*` — `dotnet restore` resolves ≥0.9.3 (PawnIO era)
3. **C# build:** `.\tools\lhm-server\build.ps1` succeeds, produces `tools/lhm-server/dist/lhm-server.exe`
4. **Integration smoke test:** Launch `lhm-server.exe` as admin, `curl http://localhost:8085/data.json` returns valid JSON with `Children`, `RawValue` fields
5. **Python sidecar:** `lhm_sidecar.py` unit tests pass — correct launch args for custom vs full LHM
6. **Full test suite:** `python -m pytest` — all 242+ tests pass
