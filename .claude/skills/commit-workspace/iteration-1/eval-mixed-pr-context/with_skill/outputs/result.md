# Questions Asked
None

# Commit Message
fix(display): detect mixed-dpi monitors with edid fallback

Adds detect_mixed_dpi() to correctly identify monitors reporting
different DPI values (e.g. 4K primary + 1080p secondary). Adds
_get_monitor_edid() with registry fallback to handle OSError on
direct EDID reads.

closes #235

# Reasoning
The branch name `feat/235-display-detection` yielded issue #235 ("Multi-monitor display detection fails for 4K + 1080p combo", labeled `bug`), and an open PR already describes the fix — so no clarifying questions were needed. The diff is small (1 file, 2 focused methods) with a single clear purpose, satisfying every skip-question condition in the skill. Type is `fix` (bug label) and scope is `display` (matching both the file and issue label); `closes` is used because the two new methods directly implement the fix described in the issue.
