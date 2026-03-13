# Product Context

## Why This Project Exists
Most gamers own powerful hardware but unknowingly leave performance on the table due to misconfigured Windows settings, outdated drivers, thermal throttling, and background bloat. Existing "PC optimizer" tools are either scamware, cloud-dependent, or require advanced technical knowledge. **lil_bro** bridges this gap as a trustworthy, fully offline AI assistant.

## Problems It Solves
- **Misconfigured display settings** — monitors running at 60Hz instead of their native 240Hz, G-Sync not properly configured
- **Suboptimal power/performance settings** — Windows defaults that throttle gaming performance (Game Mode, power plans, XMP/EXPO)
- **Input lag from low polling rates** — mice stuck at 125Hz instead of 1000Hz+
- **Thermal throttling** — overheating CPUs/GPUs silently capping performance with no user awareness
- **System bloat** — temp files, old shader caches, telemetry services consuming resources
- **Driver staleness** — outdated GPU drivers missing critical gaming optimizations

## How It Should Work
1. User downloads and runs a single `.exe` installer — no Python, Docker, or Ollama required
2. App requests admin privileges, creates a System Restore Point for safety
3. Performs a deep system scan (dxdiag, NVIDIA profile, thermal baselines)
4. Presents two pathways:
   - **Configuration Check** ("Esports Check") — audit settings and flag misconfigurations
   - **Speed Up My PC** — benchmark, debloat, fix, and re-verify
5. Every action requires **human-in-the-loop approval** before execution

## User Experience Goals
- **Zero trust required** — 100% offline, no data leaves the device
- **Safety first** — System Restore Point before any changes; clear rollback instructions
- **Approachable** — friendly language, clear explanations, no jargon walls
- **Transparent** — every proposed change is explained and requires user approval
- **One-click simplicity** — single installer, single executable, no dependencies
