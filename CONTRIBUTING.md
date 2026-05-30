# Contributing to lil_bro

Thanks for your interest in contributing to lil_bro. We appreciate bug reports, suggestions, and pull requests.

---

## How to contribute

### Issues

Bug reports, false positives, UI glitches, and accessibility problems are welcome. When opening an issue, please include:

- **What you saw** — the problem or unexpected behavior
- **What you expected** — how it should work
- **Your system details** — Windows version, GPU model, driver version
- **Steps to reproduce** (if applicable)

### Pull Requests

For anything beyond a trivial fix (typo, one-line improvement), please open an issue first so we can discuss the change before you invest time in it.

Once approved:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write or update tests to cover your changes (see [DEVELOPMENT.md](DEVELOPMENT.md) for test commands)
5. Submit a pull request with a clear description of what you changed and why

---

## Ground rules

- **Every new system check** in `src/agent_tools/` must return a structured dict with `check`, `status`, `message`, and `can_auto_fix` keys. See [DEVELOPMENT.md](DEVELOPMENT.md#writing-new-checks) for the full recipe.
- **Safety first** — every system modification must route through `prompt_approval()` before executing. No silent changes.
- **No telemetry or external APIs** — only driver version checks (NVIDIA/AMD/Intel) and the one-time GGUF model download are permitted.
- **Keep all test/sample data fictional and obviously illustrative.** Do not introduce real customer names, real metrics, or real internal data.
- **Match existing patterns.** See [DEVELOPMENT.md](DEVELOPMENT.md) for architecture, code structure, and design patterns.

---

## Developer setup

For full instructions on setting up the dev environment, running tests, and building the .exe, see [DEVELOPMENT.md](DEVELOPMENT.md).

Quick start:
```bash
uv venv
.venv/Scripts/activate
uv pip install -e ".[dev]"
python -m pytest tests/ -v
```

---

## Developer Certificate of Origin

By contributing, you certify that you have the right to submit your contribution under this project's MIT License and that you agree to license your contribution under those terms.

---

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold it.
