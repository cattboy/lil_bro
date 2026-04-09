# Questions Asked
1. What's the main goal across these changes?
2. Is this related to a specific GitHub issue?

# User's Simulated Answer
This is a broad refactor sprint — cleaning up display detection and stabilizing the thermal pipeline phases. Not tied to any specific issue.

# Commit Message
```
refactor(pipeline): clean up display detection and stabilize thermal phases

- refactored display_setter.py for multi-monitor and missing EDID fallback
- normalized monitor_dumper.py output, removed duplicate resolution fields
- improved thermal_gate.py stability for empty/partial LHM sensor data
- added shared phase status utility to base.py; propagated through baseline and final phases
- fixed phase_final.py not reporting skipped sub-steps correctly
- updated tests to match new interfaces; updated CLAUDE.md and TODOS.md
```

# Reasoning
The diff spans three distinct concerns (display detection, thermal gate stability, pipeline phase cleanup) with no single issue number in the branch name and multiple open issues that partially match — warranting the two clarifying questions per the skill's rules. The user confirmed a broad refactor sprint with no specific issue link, so no `closes`/`refs` footer is included. Scope is `pipeline` because all changed modules feed into the pipeline phases, matching the skill's own example for this exact branch pattern.
