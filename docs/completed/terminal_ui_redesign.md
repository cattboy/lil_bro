# Terminal UI Redesign — Match DESIGN.md

**Written:** 2026-03-23
**Status:** Ready to implement
**Estimated effort:** ~30 min with CC

---

## Context

The .exe is built and functional. The terminal output works but looks basic — generic colorama usage that doesn't match the design system in DESIGN.md. The design preview HTML (`docs/design-preview.html`) shows exactly how the terminal should look: accent-colored headers, dim secondary text, inline-colored audit summaries, properly formatted proposals, and casual brand voice.

**No logic changes.** Only visual output and copy.

---

## Critical Files

| File | Changes |
|------|---------|
| `src/utils/formatting.py` | Extend with 7 new functions, 1 cosmetic fix |
| `src/main.py` | 12+ visual/copy changes across banner, menu, findings, proposals, prompts |
| `src/llm/model_loader.py` | Migrate 11 direct colorama calls to formatting.py |

---

## Step 1: Extend `formatting.py`

### Modify existing:
- `print_header(title)` — change `===` to `==` to match the mockup

### Add new functions:

| Function | Purpose |
|----------|---------|
| `print_dim(msg)` | `Style.DIM` muted text (secondary info, explanations) |
| `print_accent(msg)` | `Fore.CYAN` accent text (banner subtitle, highlights) |
| `print_prompt(msg)` | Accent-colored inline prompt (`end=""`, `flush=True`) |
| `print_audit_summary(ok, warnings, unknowns)` | Compound-colored audit line: dim text with green OK count, yellow warning count |
| `print_finding(label, msg, status)` | `  [LABEL] message` — status-colored label, white message |
| `print_proposal(num, severity, title, explanation, action, can_auto_fix)` | Full proposal block: severity-colored bold header, dim explanation, fix + [AUTO]/[MANUAL] tag |
| `prompt_confirm(question)` | Branded yes/no prompt (for model download — not system modifications) |

### Signatures:

```python
def print_dim(message: str): ...
def print_accent(message: str): ...
def print_prompt(message: str): ...  # no newline, flush
def print_audit_summary(ok: int, warnings: int, unknowns: int): ...
def print_finding(label: str, message: str, status: str): ...
def print_proposal(num: int, severity: str, title: str,
                   explanation: str, action: str, can_auto_fix: bool): ...
def prompt_confirm(question: str) -> bool: ...
```

Run `python -m pytest tests/ -v` after this step.

---

## Step 2: Update `main.py`

### Banner (`print_banner`):
- ASCII art stays `Fore.MAGENTA + Style.BRIGHT` (already correct)
- Subtitle: `print_accent("  Your Local AI PC Optimization Agent")` (was magenta)
- Privacy line: `print_dim(...)` (was blue `print_info`)

### Menu (`menu_loop`):
- Accent-colored option numbers: `f"  {Fore.CYAN}1.{Style.RESET_ALL} Run Full..."`
- Input prompt: use `print_prompt()`

### Proposals (`_display_proposals`):
- Refactor to use `print_proposal()` for each item
- `[MANUAL]` tag: change from `Fore.WHITE` to `Style.DIM` to match mockup
- Still returns auto_fixable list (logic unchanged)

### Batch selection prompt:
- Use `print_prompt()` instead of inline `Fore.CYAN`

### Mouse prompt (brand voice fix):
- Old: `"PREPARE TO WIGGLE THE MOUSE FOR 3 SECONDS..."` (SHOUTING)
- New: `"Alright, wiggle your mouse for 3 seconds — we'll measure the polling rate."`
- Old: `"Press Enter to begin tracking..."`
- New: `print_prompt("Press Enter when you're ready... ")` then `input()`

### Audit summary:
- Replace `print_info(f"Audit complete: ...")` with `print_audit_summary(len(oks), len(warnings), len(unknowns))`

### Findings loop:
- Replace `print_success/warning/error` with `print_finding(check, message, status)`

### "Generating recommendations" line:
- `print_info(...)` -> `print_dim("Generating AI-powered recommendations...")`

### Ctrl+C handler:
- Inline cyan -> `print_accent(...)`

### Remove duplicate `colorama.init()`:
- formatting.py already calls `init(autoreset=True)` on import
- Remove the `colorama.init(autoreset=True)` call from `main()`

Run tests after this step.

---

## Step 3: Migrate `model_loader.py`

Replace `from colorama import Fore, Style` with formatting.py imports:

| Current | New |
|---------|-----|
| `Fore.CYAN` download header | `print_accent(...)` |
| `Fore.RED + ✗` download failed | `print_error(...)` |
| `Fore.YELLOW + ⚠` llama-cpp warning | `print_warning(...)` |
| `Fore.CYAN === First Run ===` header | `print_header(...)` |
| `Fore.YELLOW` privacy note | `print_warning("Privacy note:")` |
| `Fore.MAGENTA` download prompt | `prompt_confirm("Download model now?")` |
| `Fore.YELLOW + ⚠` skip message | `print_warning(...)` |
| `Fore.GREEN + ✓` cache success | `print_success(...)` |
| `Fore.BLUE + ℹ` loading (no newline) | `print_step("Loading AI model (CPU)")` |
| `Fore.GREEN` "Ready." | `print_step_done(True)` |
| `Fore.RED + ✗` load failure | `print_error(...)` |

Keep the download progress `\r` print as-is (special-purpose progress indicator).

Run tests after this step.

---

## Verification

1. `python -m pytest tests/ -v` — all 164 tests pass
2. Visual spot-check (`python -m src.main`):
   - Banner: magenta art, cyan subtitle, dim privacy line
   - Menu: accent-numbered items, cyan input prompt
   - Phase headers: `== Title ==` in cyan+bright
   - Findings: colored bracket labels, white message text
   - Proposals: severity-colored bold headers, dim explanations, green [AUTO] / dim [MANUAL]
   - Mouse prompt: casual voice, not SHOUTING

## Test Impact

**Zero breakage expected:**
- No tests import formatting.py directly
- Tests mock `prompt_approval` at caller namespace (e.g., `@patch('src.bootstrapper.prompt_approval')`)
- No tests use `capsys`/`capfd` to capture stdout
- All new functions are additive
- `print_header` delimiter change is cosmetic — no test asserts on the printed string

---

## DESIGN.md Color Reference

```
Fore.CYAN    → accent (#00E5CC)
Fore.GREEN   → success (#4ADE80)
Fore.YELLOW  → warning (#FFB547)
Fore.RED     → error (#FF6B6B)
Fore.MAGENTA → brand/banner (#D183E8)
Fore.WHITE   → text primary
Style.DIM    → text muted
```
