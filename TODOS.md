# TODOS

Items flagged during reviews but deferred from current PRs.
Format: Priority | Effort (human / CC) | Context

---

## Open

### T-001 — Future-proof formatting.py API for rich/GUI backend
**Priority:** P2
**Effort:** L human / M with CC
**Why:** All `print_*` functions in `formatting.py` call `print()` directly and are tightly coupled to colorama. When the PyQt GUI arrives (planned, deferred), a GUI layer would need to intercept terminal output and display it in a widget instead. A `return_str=False` default param on each function enables this without changing any call sites.
**How to apply:** Add `return_str: bool = False` param to all print_* functions. When `True`, return the formatted string instead of printing. The GUI backend calls them with `return_str=True`; the terminal path stays unchanged.
**Blocked by:** PyQt GUI architecture decision (Phase 5).
**Added:** 2026-03-24 (from /plan-ceo-review, Week 6 terminal UI redesign)

---

### T-002 — Harden LLM output printing against UnicodeEncodeError
**Priority:** P2
**Effort:** S human / S with CC
**Why:** `print_proposal` and other functions pass LLM-generated text directly to `print()`. On Windows CMD (CP437 encoding), any character outside the CP437 charset raises `UnicodeEncodeError` — a silent crash with no user-friendly message. Qwen2.5 can produce non-Latin characters even in English responses.
**Fix options:**
1. Set `PYTHONIOENCODING=utf-8` in the launcher script / `.spec` file
2. Wrap `sys.stdout` at startup: `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')`
**Recommended:** Option 2 (runtime fix, no launcher dependency).
**Added:** 2026-03-24 (from /plan-ceo-review, Week 6 terminal UI redesign)

---

## Completed

*(none yet)*
