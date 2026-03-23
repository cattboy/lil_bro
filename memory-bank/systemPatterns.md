# System Patterns

## Architecture Overview
```
┌─────────────────────────────────────────────┐
│        PyInstaller Portable .exe             │
│  (single lil_bro.exe + integrity.json)       │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           Python Orchestrator                │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │BootStrapper│  │ Scanner  │  │ UI Layer  │  │
│  │(UAC, SRP)  │  │(dxdiag,  │  │(Terminal) │  │
│  │           │  │ WMI, LHM)│  │           │  │
│  └──────────┘  └──────────┘  └───────────┘  │
│              ┌──────────┐                    │
│              │ LLM Brain │                   │
│              │(llama-cpp)│                   │
│              └──────────┘                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │Benchmark  │  │ Debloater│  │ Thermal   │  │
│  │Runner     │  │ Module   │  │ Monitor   │  │
│  └──────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────┘
```

## Key Technical Decisions
| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM Runtime | `llama-cpp-python` | Run GGUF models natively in Python, no external server |
| Model | `Qwen2.5-Coder-7B-Instruct.Q4_K_M` | Small (~4.5 GB), strong at JSON/logic/code tasks |
| UI Framework | Terminal + optional PyQt | Keep simple, upgrade path available |
| Packaging | PyInstaller (onefile) | Portable .exe — double-click and go, no installer |
| Bundler | PyInstaller | Compile Python to standalone executable |
| Temp Monitoring | LibreHardwareMonitor | Open-source, no licensing issues |
| GPU Profiling | NvidiaProfileInspector | Community-standard NVIDIA tweaking tool |

## Design Patterns
- **ReAct Loop** — Reasoning & Acting pattern for the "Speed Up My PC" workflow: observe → reason → propose → approve → act → verify
- **Human-in-the-Loop** — Every destructive action requires explicit user approval
- **Safety-First Bootstrapping** — System Restore Point created before any modifications
- **Integrity Verification** — File hashing on initial run to detect corruption
- **Modular Scanning** — Each check (refresh rate, polling rate, power plan, etc.) is an independent module

## Component Relationships
- **Bootstrapper** → creates safety net, triggers deep scan
- **Scanner** → feeds system data to LLM Brain
- **LLM Brain** → analyzes data, generates action proposals as JSON
- **UI Layer** → presents proposals to user, captures approvals
- **Benchmark Module** → executes benchmarks, feeds results to LLM Brain
- **Debloater Module** → executes approved cleanup actions
- **Thermal Monitor** → runs during benchmarks, feeds temps to LLM Brain for diagnosis
