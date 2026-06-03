"""Meta-test: double-check that every source module has its required test cases.

This is a *ratchet*, not a coverage percentage. It statically maps every module
under ``src/`` to the test suite and fails when a substantive module has **no
dedicated test reference**. A module counts as covered when either:

  1. A test file imports it directly
     (``import src.x.y`` / ``from src.x.y import Z`` / ``from src.x import y``), or
  2. It is re-exported through a package ``__init__.py`` that a test imports
     (the public API is exercised through the package surface).

Transitive imports through *production* code do **not** count: ``stylesheet.py``
importing ``stylesheet_dialogs`` means the latter runs, not that it is tested.

Modules that intentionally lack a dedicated test live in ``ALLOWLIST`` below,
each with a reason. The allowlist is the ledger of known gaps — shrink it as
tests are added. Two guard tests keep it honest: it may not contain stale
entries (modules that *are* now referenced) or dangling ones (deleted modules).

Run as a report (no pytest):
    python tests/test_module_test_coverage.py
"""

from __future__ import annotations

import ast
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
TESTS_ROOT = PROJECT_ROOT / "tests"

# Structural modules that never carry their own logic and so never need a
# dedicated test: package markers and the single-line version string.
_STRUCTURAL_SUFFIXES = ("__init__", "._version", ".__main__")

# ---------------------------------------------------------------------------
# Known gaps. Each entry is a module that currently has no dedicated test,
# with the reason. Adding a NEW substantive module without a test should fail
# this suite — extend the test suite, do not extend this list casually.
# ---------------------------------------------------------------------------
ALLOWLIST: dict[str, str] = {
    # Exercised transitively through src.benchmarks.cinebench; no dedicated
    # unit test for the split-out helpers yet.
    "src.benchmarks.cinebench_discovery": "helper of cinebench.py; no dedicated test",
    "src.benchmarks.cinebench_monitor": "helper of cinebench.py; no dedicated test",
    "src.benchmarks.cinebench_parser": "helper of cinebench.py; no dedicated test",
    # Sub-dumpers driven through src.collectors.spec_dumper. Vendor-specific
    # output parsing is covered indirectly via test_spec_dumper / test_dump_parser.
    "src.collectors.sub.amd_smi_dumper": "sub-dumper of spec_dumper.py; no dedicated test",
    "src.collectors.sub.dxdiag_dumper": "sub-dumper of spec_dumper.py; no dedicated test",
    "src.collectors.sub.libra_hm_dumper": "sub-dumper of spec_dumper.py; no dedicated test",
    "src.collectors.sub.wmi_dumper": "sub-dumper of spec_dumper.py; no dedicated test",
    "src.collectors.sub.lhm_discovery": "LHM helper exercised via test_lhm_sidecar; no dedicated test",
    "src.collectors.sub.lhm_http": "LHM helper exercised via test_lhm_sidecar; no dedicated test",
    # QSS string builders, exercised through src.gui.theme.stylesheet (which
    # test_theme drives via build_stylesheet). No per-module test.
    "src.gui.theme.stylesheet_dialogs": "QSS builder under theme.stylesheet; covered via test_theme",
    "src.gui.theme.stylesheet_foundation": "QSS builder under theme.stylesheet; covered via test_theme",
    "src.gui.theme.stylesheet_interactive": "QSS builder under theme.stylesheet; covered via test_theme",
    "src.gui.theme.stylesheet_monitoring": "QSS builder under theme.stylesheet; covered via test_theme",
    # Thin Qt signal-wiring / widget glue; no isolated test yet.
    "src.gui.pipeline_controller": "Qt signal wiring glue; no dedicated test",
    "src.gui.widgets.mouse_ready_dialog": "simple dialog widget; no dedicated test",
    "src.gui.widgets.output_view": "simple view widget; no dedicated test",
    # Heavy/offline GGUF loader — hard to unit-test without a model on disk.
    "src.llm.model_loader": "GGUF loader; needs model artifact, no dedicated test",
    # Low-level utility helpers.
    "src.utils._console": "console helper; no dedicated test",
    "src.utils.integrity": "hashing/integrity util; no dedicated test",
}


def _dotted(path: pathlib.Path) -> str:
    """``src/gui/app.py`` -> ``src.gui.app``."""
    return ".".join(path.relative_to(PROJECT_ROOT).with_suffix("").parts)


def _module_imports(path: pathlib.Path, pkg: str | None) -> set[str]:
    """Dotted module names referenced by the file's import statements.

    ``pkg`` is the package the file belongs to, used to resolve relative
    (``from . import x``) imports inside ``__init__.py`` files.
    """
    refs: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                refs.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and pkg is not None:
                base = pkg if node.module is None else f"{pkg}.{node.module}"
                refs.add(base)
                for alias in node.names:
                    refs.add(f"{base}.{alias.name}")
            elif node.module:
                refs.add(node.module)
                # `from pkg import submodule` also references `pkg.submodule`.
                for alias in node.names:
                    refs.add(f"{node.module}.{alias.name}")
    return refs


def discover_src_modules() -> set[str]:
    """All substantive (non-structural) modules under ``src/``."""
    return {
        _dotted(p)
        for p in SRC_ROOT.rglob("*.py")
        if not _dotted(p).endswith(_STRUCTURAL_SUFFIXES)
    }


def referenced_modules() -> set[str]:
    """Modules reachable from the test suite via direct imports or tested
    package ``__init__`` re-exports."""
    referenced: set[str] = set()
    for test_file in TESTS_ROOT.rglob("*.py"):
        referenced |= _module_imports(test_file, pkg=None)

    # Expand through __init__ re-exports to a fixed point: if a test imports a
    # package and that package's __init__ re-exports a submodule, the submodule
    # is exercised through the package's public API.
    init_refs: dict[str, set[str]] = {}
    for init_path in SRC_ROOT.rglob("__init__.py"):
        pkg = _dotted(init_path).rsplit(".__init__", 1)[0]
        init_refs[pkg] = _module_imports(init_path, pkg=pkg)

    changed = True
    while changed:
        changed = False
        for pkg, refs in init_refs.items():
            if pkg in referenced:
                for ref in refs:
                    if ref not in referenced:
                        referenced.add(ref)
                        changed = True
    return referenced


def unreferenced_modules() -> set[str]:
    """Substantive src modules with no dedicated test reference."""
    return discover_src_modules() - referenced_modules()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_every_src_module_has_a_test_reference() -> None:
    """Fail if a substantive module has no dedicated test and is not an
    acknowledged gap in ALLOWLIST."""
    missing = sorted(unreferenced_modules() - set(ALLOWLIST))
    assert not missing, (
        "These src modules have no dedicated test reference and are not in the "
        "ALLOWLIST. Add a test (preferred) or, if intentionally untested, add "
        "the module to ALLOWLIST in tests/test_module_test_coverage.py with a "
        "reason:\n  " + "\n  ".join(missing)
    )


def test_allowlist_has_no_stale_entries() -> None:
    """An allowlisted module that is now referenced should be removed from the
    ledger so the gap list stays accurate."""
    referenced = referenced_modules()
    stale = sorted(m for m in ALLOWLIST if m in referenced)
    assert not stale, (
        "These modules now have a test reference — remove them from ALLOWLIST "
        "in tests/test_module_test_coverage.py:\n  " + "\n  ".join(stale)
    )


def test_allowlist_has_no_dangling_entries() -> None:
    """An allowlisted module that no longer exists (renamed/deleted) should be
    pruned from the ledger."""
    existing = discover_src_modules()
    dangling = sorted(m for m in ALLOWLIST if m not in existing)
    assert not dangling, (
        "These ALLOWLIST modules no longer exist under src/ — remove them from "
        "tests/test_module_test_coverage.py:\n  " + "\n  ".join(dangling)
    )


if __name__ == "__main__":  # `python tests/test_module_test_coverage.py`
    src = discover_src_modules()
    unref = unreferenced_modules()
    gaps = sorted(unref & set(ALLOWLIST))
    failures = sorted(unref - set(ALLOWLIST))
    covered = len(src) - len(unref)
    print(f"src modules (substantive): {len(src)}")
    print(f"  covered by a test:       {covered}")
    print(f"  acknowledged gaps:       {len(gaps)}")
    print(f"  UNCOVERED (no allowlist): {len(failures)}")
    if gaps:
        print("\nAcknowledged gaps (ALLOWLIST):")
        for m in gaps:
            print(f"  - {m}  # {ALLOWLIST[m]}")
    if failures:
        print("\n*** UNCOVERED modules (would fail the suite) ***")
        for m in failures:
            print(f"  - {m}")
    raise SystemExit(1 if failures else 0)
