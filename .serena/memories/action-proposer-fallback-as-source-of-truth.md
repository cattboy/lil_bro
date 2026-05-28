# Reuse `action_proposer.py` for dashboard tile text — convention

When a Dashboard card needs to display a FAIL-tier explanation or proposed action (mouse polling below 500Hz, monitor at sub-optimal refresh rate, etc.), pull the text from `FALLBACK_PROPOSALS` via `propose_for_check()` instead of hardcoding it in the widget. **The LLM is never loaded in the GUI path** — templates are the product on dashboard.

## Why this pattern exists

Before consolidation (refactor landed 2026-05-18), the same `mouse_polling` and `display` check had two parallel sets of user-facing copy:
1. `_FALLBACK["mouse_polling"]` / `_FALLBACK["display"]` in `action_proposer.py` (used by terminal pipeline approval flow).
2. Hardcoded strings inside `Dashboard._update_poll_display`, `Dashboard._on_mouse_done`, and `MonitorRefreshCard.set_display` (used by GUI dashboard).

Copy edits in one place left the other drifted. Three places to remember on every text change.

## The convention

```python
from src.llm.action_proposer import propose_for_check

# Inside the widget's update method, FAIL branch only:
proposal = propose_for_check("mouse_polling",
    {"current_hz": hz, "threshold_hz": 500})
self._status_lbl.setText(proposal["proposed_action"])  # ~8-10 word tile text
self._status_lbl.setToolTip(proposal["explanation"])   # ~25-30 word full text on hover
self._set_poll_sev("high")  # sev coloring is still widget-side
```

- `proposed_action` is short (5-14 words) — fits on dashboard tiles.
- `explanation` is long (25-30 words) — lives in `setToolTip()` for hover-reveal.
- **OK-tier** branches (Hz ≥ 500, monitor at optimal) keep their own live commentary strings inline. `FALLBACK_PROPOSALS` is FAIL-only by design.
- **Pass** branches (✓ at max refresh) and **structural** copy (WMI diagnostic text) are also kept inline — they are not proposals.

## `propose_for_check()` API

`src/llm/action_proposer.py:propose_for_check(check, finding=None, llm=None)`:
- `finding=None` → returns the FALLBACK_PROPOSALS entry directly (static-text widgets).
- `finding=dict` → wraps `propose_actions(hardware={}, findings=[full], llm=llm)` and returns the first proposal.
- `llm=None` (default for GUI) → fallback template path, microsecond-fast, no model load.

`hardware={}` is safe because `_build_fallback` ignores hardware; only `build_llm_input` reads it (LLM path only).

## Three things that bite

1. **Don't call this on OK tiers.** `FALLBACK_PROPOSALS` is FAIL-only, but `propose_for_check` forces `status="WARNING"` on its input — it will always return a proposal even for an OK measurement. Gate the call behind your own FAIL branch.
2. **Don't add new Fix buttons reflexively.** `MonitorRefreshCard` already has one (`fix_requested` signal → `_on_monitor_fix_requested` in `app.py`). `mouse_polling.can_auto_fix=False` → no button. Check `can_auto_fix` first.
3. **Don't load the LLM in the GUI just to enrich tile copy.** The 4.5 GB GGUF model + 2-4s cold load isn't warranted for narrow tile text. If LLM-personalized text is wanted later, `propose_for_check(check, finding, llm=…)` already accepts an LLM — wire it in then, not preemptively.

## File locations

- `src/llm/action_proposer.py:130` — `FALLBACK_PROPOSALS` dict (public; renamed from `_FALLBACK` on 2026-05-18)
- `src/llm/action_proposer.py:263+` — `propose_for_check()` helper
- `src/gui/widgets/dashboard.py` — `_update_poll_display`, `_on_mouse_done` (consumers)
- `src/gui/widgets/monitor_refresh_card.py` — `set_display` suboptimal branch (consumer)
- `tests/test_action_proposer_gui.py` — 5 unit tests pinning the contract

## Cross-references

- Sev coloring is still set by the widget (not by the proposer) — see Claude memory `feedback_design_sev_color_system.md` for the `sev=low|medium|high` QSS property convention.
- Adding a new dashboard card → see Claude memory `feedback_dashboard_card_pattern.md` Step 4 (text source now goes through `propose_for_check`).
- Plan that landed this refactor: `C:\Users\Owner\.claude\plans\make-a-new-plan-streamed-valley.md` (Plan v2, sonnet-reviewed).
