# Questions Asked
None

# Commit Message
fix(thermal): handle empty and invalid LHM sensor data gracefully

When LHM returns an empty sensor list or sensors with zero values,
thermal_gate.py raised a TypeError instead of handling the absence
cleanly. Return None instead so callers can decide how to proceed.

closes #456

# Reasoning
The branch name `fix/456-thermal-crash` directly encodes issue number 456, and the issue title ("Thermal gate crashes when LHM returns empty sensor list") precisely matches the diff — no clarifying questions are needed per the skill's rules (issue found, diff is small and single-purpose, ≤3 files). The fix replaces a hard `TypeError` raise with a `return None` guard and adds non-empty/non-zero checks, fully resolving the issue, so `closes #456` is the correct reference. Scope is `thermal` to match the changed module.
