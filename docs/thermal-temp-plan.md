# Plan: Fix lhm-server sidecar launch failure

## Context

Commits `b9746f4` and `d4dabb3` integrated PawnIO into the lhm-server build chain. The built `.exe` fails at runtime:

```
• Launching lhm-server sidecar... Failed!
⚠ LibreHardwareMonitor launched but /data.json not reachable after 5s.
```

The sidecar finds and launches `lhm-server.exe`, but the HTTP health check times out after 5 seconds. Four bugs in `lhm_sidecar.py` combine to cause this failure and hide the root cause.

---

## Bugs Found

| # | Bug | Impact |
|---|-----|--------|
| 1 | **No process liveness check** during health poll — waits full 5s even if process crashed instantly | Wastes time, hides crash |
| 2 | **stderr suppressed** (`subprocess.DEVNULL`) — crash output completely lost | Zero diagnostics |
| 3 | **`self._process.pid` crash** when launched via ShellExecuteW (elevated) — `_process` is None | AttributeError on success path |
| 4 | **5s timeout too short** for .NET self-contained cold start (runtime extraction + PawnIO install + LHM init) | False timeout on healthy slow start |

**Build chain note:** `tools/PawnIO/dist/` does not exist — PawnIO.sys was never built (requires WDK + CMake + test-signing). The `.csproj` `Condition="Exists(...)"` silently skipped embedding. This is a prerequisite issue, not a code bug — document it, don't try to fix the WDK build chain.

---

## Changes

### File: `src/collectors/sub/lhm_sidecar.py`

**1. Add `import threading`** (line 9 area)

**2. Increase timeout** (line 25)
```python
# Before:
_STARTUP_TIMEOUT = 5
# After:
_STARTUP_TIMEOUT = 15  # .NET self-contained cold start needs extraction + init
```

**3. Add `_stderr_lines` to `__init__`** (after line 124)
```python
self._stderr_lines: list[str] = []
```

**4. Capture stderr from subprocess** (line 187)
```python
# Before:
stderr=subprocess.DEVNULL,
# After:
stderr=subprocess.PIPE,
```

**5. Start drain thread after Popen** (after line 189)
```python
threading.Thread(target=self._drain_stderr, daemon=True).start()
```

**6. Add `_drain_stderr` method** (new method on LHMSidecar)
```python
def _drain_stderr(self) -> None:
    """Read stderr from subprocess into _stderr_lines (daemon thread)."""
    proc = self._process
    if proc is None or proc.stderr is None:
        return
    try:
        for raw_line in proc.stderr:
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            if line:
                self._stderr_lines.append(line)
    except (ValueError, OSError):
        pass  # pipe closed on normal shutdown
```

**7. Restructure health poll loop** (lines 216-234) — add liveness check, fix PID crash, add stderr dump on failure:
```python
deadline = time.monotonic() + _STARTUP_TIMEOUT
while time.monotonic() < deadline:
    if _is_lhm_responding():
        print_step_done(True)
        pid_str = str(self._process.pid) if self._process else "elevated"
        action_logger.log_action(
            "LHM Sidecar", f"Launched (PID {pid_str})", f"Port {LHM_PORT}"
        )
        return True
    # Early exit if subprocess already died
    if self._process is not None and self._process.poll() is not None:
        rc = self._process.returncode
        print_step_done(False)
        print_warning(
            f"lhm-server.exe exited immediately (exit code {rc}). "
            "Thermal monitoring unavailable."
        )
        if self._stderr_lines:
            for line in self._stderr_lines[-10:]:
                print_dim(f"  [lhm-server] {line}")
        self._process = None
        return False
    time.sleep(_POLL_INTERVAL)

# Timeout — process alive but HTTP never became ready
print_step_done(False)
print_warning(
    f"LibreHardwareMonitor launched but /data.json not reachable after "
    f"{_STARTUP_TIMEOUT}s. Thermal monitoring unavailable."
)
if self._stderr_lines:
    for line in self._stderr_lines[-10:]:
        print_dim(f"  [lhm-server] {line}")
self._kill_process()
return False
```

**8. Update module docstring** — add PawnIO build prerequisite note.

**9. Add `print_dim` to imports** (line 19) — not currently imported. Add to the existing formatting import line:
```python
from ...utils.formatting import print_step, print_step_done, print_warning, print_info, print_dim
```

---

### File: `tests/test_lhm_sidecar.py`

**Update existing tests** (mock Popen now uses `stderr=PIPE` + drain thread):

| Test | Changes needed |
|------|---------------|
| `test_start_launches_full_lhm_successfully` (L118) | Add `mock_proc.stderr = None`, `mock_proc.poll.return_value = None` |
| `test_start_launches_custom_server_no_port_flag` (L144) | Add `mock_proc.stderr = None`, `mock_proc.poll.return_value = None` |
| `test_start_launch_timeout` (L173) | Add `mock_proc.stderr = None`, `mock_proc.poll.return_value = None`, change `[0.0, 6.0]` → `[0.0, 0.5, 16.0]` |
| `test_popen_stdin_is_devnull` (L267) | Add `mock_proc.stderr = None` |

**Why `stderr = None`:** Without this, MagicMock auto-generates a truthy `.stderr` attribute. The drain thread would iterate it infinitely (MagicMock's `__iter__` yields infinite MagicMocks). Setting `None` triggers the early return in `_drain_stderr`.

**Why `poll.return_value = None`:** MagicMock's `.poll()` returns a truthy MagicMock by default, which would trigger the early-exit crash detection path. Setting `None` simulates "process still running".

**Add new tests:**

1. **`test_start_early_exit_on_crash`** — `poll()` returns exit code immediately → `start()` returns `False` without waiting full timeout
2. **`test_stderr_captured_on_crash`** — verify stderr lines appear in output on process crash

---

## Verification

1. `source .venv/Scripts/activate && python -m pytest tests/test_lhm_sidecar.py -v` — all tests pass
2. `source .venv/Scripts/activate && python -m pytest tests/ -v` — full suite (264+ tests) passes
3. Manual: `python build.py` → run `dist/lil_bro.exe` → observe diagnostic output if lhm-server crashes (stderr lines printed) or successful startup if PawnIO is available

---

## Files Modified

- `src/collectors/sub/lhm_sidecar.py` — all runtime fixes
- `tests/test_lhm_sidecar.py` — test updates + new tests
