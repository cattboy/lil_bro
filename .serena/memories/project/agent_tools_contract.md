---
name: agent_tools_contract
description: Return dict schema and safety gate every agent_tools check and setter must follow — validated by safety-reviewer agent
type: project
---

# Agent Tools Contract

Every file in `src/agent_tools/` must follow this contract.

## Check functions

Return a structured dict:
```python
{
    "status": "OK" | "WARN" | "FAIL" | "SKIPPED",
    "message": str,
    # ...additional fields as needed
}
```

No side effects. No system calls that modify state. Pure read + analysis only.

## Setter functions

- Raise `SetterError` (from `src/utils/errors.py`) on failure — never return silently or raise bare `Exception`
- Never apply changes directly — all mutations must be routed through the approval gate below

## Safety gate (non-negotiable)

Every system modification must be routed through:
1. `fix_dispatch` registry in `src/pipeline/fix_dispatch.py` — maps check name → setter function
2. `run_approval_flow` in `src/pipeline/approval.py` — calls `prompt_approval()` to get user consent before executing

**No direct system modifications outside this gate.** The `safety-reviewer` Claude Code agent audits this contract and flags any bypass.

## Existing check/setter pairs (reference)
- `display.py` / `display_setter.py` — refresh rate
- `power_plan.py` — power plan detection + switching
- `game_mode.py` — Windows Game Mode registry
- `nvidia_profile.py` / `nvidia_profile_setter.py` — NVIDIA Profile Inspector settings
- `xmp_check.py` — RAM XMP/EXPO (read-only)
- `rebar.py` — Resizable BAR (read-only)
- `temp_audit.py` — temp folder bloat + cleanup
- `mouse.py` — mouse polling rate (read-only)
- `thermal_guidance.py` — thermal analysis (read-only)
