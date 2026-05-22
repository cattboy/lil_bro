## lil_bro.spec Audit — May 2026

**Question:** Is `src.gui.theme` dead code in the spec? Any other stale modules?

**Answer:** No dead code in spec. All 25 hiddenimport entries point to real files.

### The src.gui.theme confusion
- `theme.py` was refactored into a package (`src/gui/theme/`)
- Spec entry `src.gui.theme` still resolves to `src/gui/theme/__init__.py` — valid and correct
- The `__init__.py` re-exports all public symbols (COLORS, FONTS, build_stylesheet, repolish, load_fonts)
- All imports across the codebase (`from src.gui.theme import ...`) resolve correctly
- Submodules (helpers, stylesheet, tokens) are imported at module level in `__init__.py`, so PyInstaller's static analysis reaches them automatically

### Real bug found and fixed
Two GUI modules extracted from `app.py`'s `run()` in commit 3f6b99c were missing from hiddenimports:
- `src.gui.pipeline_controller` (imported app.py:24)
- `src.gui.startup_coordinator` (imported app.py:27)

**Fix applied:** Added both to spec, alphabetized the entire src.gui.* block.

The modules are imported at top level (not lazily), so PyInstaller *should* follow them from app.py, but the CLAUDE.md rule says "every new gui module must be in hiddenimports" for safety against future refactors. Spec now compliant.

**Build result:** exit code 0, exe size 92 MB (normal).

No further changes needed. Spec is clean.
