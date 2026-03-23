# Tech Context

## Technologies Used
| Category | Technology | Version/Notes |
|----------|-----------|---------------|
| Language | Python 3 | Core orchestrator |
| LLM Runtime | `llama-cpp-python` | Runs GGUF models in-process |
| LLM Model | `Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf` | ~4.5 GB, downloaded on first run from HuggingFace (optional) |
| System Info | WMI (`wmi` package) | Windows Management Instrumentation queries |
| System Info | `dxdiag` | DirectX Diagnostic Tool (built-in) |
| GPU Profiling | NvidiaProfileInspector | Bundled executable |
| Thermal Monitoring | LibreHardwareMonitor | Bundled executable, open-source |
| UI | Terminal / PyQt | Terminal-first, PyQt optional upgrade |
| Bundler | PyInstaller | Compiles Python to standalone `.exe` |
| Packaging | PyInstaller (onefile) | Portable .exe, no installer needed |

## Development Setup
- **OS:** Windows 10/11 (target platform)
- **Python:** 3.11+ recommended
- **IDE:** Any (VS Code recommended)
- **Admin rights:** Required for testing system modification features

## Technical Constraints
- **Fully offline** — no cloud APIs, no telemetry, no network calls except driver version checks
- **Single portable .exe** — user must not need to install Python, Docker, Ollama, or any other dependency
- **Admin required** — System Restore Point and many optimizations need elevated privileges
- **GPU VRAM** — Qwen2.5-Coder-7B Q4 needs ~4.5 GB; system must have enough RAM/VRAM
- **Windows only** — WMI, registry, dxdiag, PowerShell are all Windows-specific

## Dependencies (Python Packages)
- `colorama` — terminal color output
- `wmi` — Windows Management Instrumentation
- `psutil` — cross-platform process and system utilities
- `llama-cpp-python` — local LLM inference (optional — tool works without it)
- `pyinstaller` — .exe packaging (dev dependency)
- `pytest` — testing (dev dependency)

## External Tools
- `LibreHardwareMonitor` — hardware sensor monitoring (bundled sidecar, Week 3)
- `NvidiaProfileInspector` — NVIDIA profile import/export (deferred to future version)
- `dxdiag` — system-provided DirectX diagnostics (built-in to Windows)

## Tool Usage Patterns
- **PowerShell** — System Restore Point creation, registry modifications
- **WMI** — querying `Win32_VideoController`, memory speed, display settings
- **Registry** — checking Game Mode, EDID keys, refresh rate overrides
- **Win32 API** — `GetMouseMovePointsEx` for mouse polling rate detection
