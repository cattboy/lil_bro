"""AST guard: every subprocess call in src/ must suppress its console window.

lil_bro.exe is built console=False (GUI subsystem). Any child console process
spawned without creationflags=CREATE_NO_WINDOW (or a hidden STARTUPINFO)
allocates its own visible console window -- the "flashing cmd windows" bug.

These tests enforce, for every *.py under src/:
  1. every direct subprocess.run/Popen/check_output/check_call/call passes a
     ``creationflags=`` or ``startupinfo=`` keyword;
  2. no evasion vectors exist: ``from subprocess import run/...``,
     ``import subprocess as alias``, or ``os.system/os.popen/os.startfile/
     os.spawn*`` (which would dodge check 1's attribute matching).

Known limitations (by design):
  - Presence-only: a STARTUPINFO without wShowWindow=SW_HIDE would pass. The
    one STARTUPINFO site (cinebench's vendor-required real-console launch)
    has its value semantics pinned by test_benchmark_runner.py's D6 test,
    which asserts that Popen must NOT use CREATE_NO_WINDOW.
  - multiprocessing/ProcessPoolExecutor are not covered (unused in src/ --
    main.py has only freeze_support(); frozen children would inherit
    console=False anyway).
"""

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"

_SUBPROCESS_SPAWNERS = {"run", "Popen", "check_output", "check_call", "call"}

# (path relative to repo root, substring of the offending call's source).
# Each entry needs a reason for being visible.
_ALLOWLIST = {
    # System Restore GUI the user is meant to see and interact with during
    # revert. GUI-subsystem exe -- never allocates a console, so no flash.
    ("src/utils/revert.py", "rstrui.exe"),
}

_OS_SPAWNERS = {
    "system", "popen", "startfile",
    "spawnl", "spawnle", "spawnlp", "spawnlpe",
    "spawnv", "spawnve", "spawnvp", "spawnvpe",
}


def _src_files() -> list[Path]:
    files = sorted(_SRC.rglob("*.py"))
    assert files, f"no Python files found under {_SRC}"
    return files


def _rel(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def test_every_subprocess_call_suppresses_its_console_window():
    offenders = []
    for path in _src_files():
        source = path.read_text(encoding="utf-8-sig")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
                and func.attr in _SUBPROCESS_SPAWNERS
            ):
                continue
            kwarg_names = {kw.arg for kw in node.keywords}
            if "creationflags" in kwarg_names or "startupinfo" in kwarg_names:
                continue
            segment = ast.get_source_segment(source, node) or ""
            if any(
                rel == _rel(path) and marker in segment
                for rel, marker in _ALLOWLIST
            ):
                continue
            offenders.append(f"{_rel(path)}:{node.lineno}  subprocess.{func.attr}(...)")
    assert not offenders, (
        "subprocess call(s) without creationflags=CREATE_NO_WINDOW or a hidden "
        "STARTUPINFO -- each flashes a console window in GUI mode "
        "(import CREATE_NO_WINDOW from src.utils.subprocess_utils):\n  "
        + "\n  ".join(offenders)
    )


def test_no_window_suppression_evasion_vectors():
    offenders = []
    for path in _src_files():
        source = path.read_text(encoding="utf-8-sig")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                spawners = {a.name for a in node.names} & _SUBPROCESS_SPAWNERS
                if spawners:
                    offenders.append(
                        f"{_rel(path)}:{node.lineno}  from subprocess import "
                        + ", ".join(sorted(spawners))
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "subprocess" and alias.asname:
                        offenders.append(
                            f"{_rel(path)}:{node.lineno}  import subprocess as {alias.asname}"
                        )
            elif isinstance(node, ast.Call):
                func = node.func
                if (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "os"
                    and func.attr in _OS_SPAWNERS
                ):
                    offenders.append(f"{_rel(path)}:{node.lineno}  os.{func.attr}(...)")
    assert not offenders, (
        "process-spawn evasion vector(s) found -- these dodge the AST guard in "
        "test_every_subprocess_call_suppresses_its_console_window and can flash "
        "console windows; spawn via `subprocess.<fn>(..., "
        "creationflags=CREATE_NO_WINDOW)` instead:\n  " + "\n  ".join(offenders)
    )
