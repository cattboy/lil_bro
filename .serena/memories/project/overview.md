# lil_bro — Project Overview

**Purpose**: Local, privacy-first AI agent for gaming PC optimization. Analyzes system configurations, detects misconfigurations, and applies targeted fixes with user approval. 100% offline — no data leaves the device.

**Entry point**: `src/main.py` → `src/pipeline/phases.py` → 5 phase files → `src/agent_tools/` checks

**Pipeline phases**:
1. Bootstrap — admin check, restore point, LHM sidecar start
2. Scan — collect hardware specs (WMI, nvidia-smi, dxdiag, LHM, etc.)
3. Baseline benchmark — Cinebench or CPU stress fallback, thermal monitoring
4. Config/Analysis — LLM or static proposal, human approval, fix dispatch
5. Final benchmark — re-run benchmark, compare delta

**Key constraint**: Every system modification must call `prompt_approval()` before executing — no silent changes.
