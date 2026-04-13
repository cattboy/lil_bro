# Questions Asked
None

# Commit Message
fix(thermal-gate): return None instead of raising on missing sensor data

Replace TypeError raise with a None return when sensor data is absent or
yields no valid temperatures. Also guard against all-zero temperature
readings so the gate doesn't treat zeroed-out sensors as valid data.

# Reasoning
The diff converts a hard crash (TypeError) into a graceful no-op (return None) and tightens the validity check on temperature values, which is a targeted bug fix scoped to the thermal gate component.
