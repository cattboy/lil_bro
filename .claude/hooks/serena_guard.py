#!/usr/bin/env python3
"""
Serena Guard — PreToolUse hook.

Blocks Read / Edit / Write / Grep / Glob calls that target Python source
files and reminds Claude to use the appropriate Serena MCP tool instead.
Also blocks Bash in-place edits of .py files (sed -i, output redirects,
tee, awk -i inplace, perl -i), so structural code changes go through
Serena's symbol tools.

Carve-out: `.claude/hooks/` paths are infrastructure (not project Python)
and Serena cannot extract symbols from module-level scripts, so hook
files are not gated by themselves. This keeps the hook editable via any
tool without having to disable itself.

Exit codes:
  0 — allow the tool call to proceed
  2 — block the tool call; stderr is shown to the model as feedback
"""
import json
import re
import sys
from pathlib import Path

data = json.load(sys.stdin)
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})


def _is_hook_path(text: str) -> bool:
    return ".claude/hooks/" in text.replace("\\", "/")


blocked = False
suggestion = ""

if tool_name in ("Read", "Edit", "Write"):
    path = str(tool_input.get("file_path", ""))
    if path.endswith(".py") and not _is_hook_path(path):
        # Carve-out: allow Write to a path that does not yet exist.
        # Serena runs with --context claude-code, which deliberately
        # excludes create_text_file (see claude-code.yml in the Serena
        # install) — net-new file creation is the IDE's job.
        is_new_file_write = tool_name == "Write" and not Path(path).exists()
        if not is_new_file_write:
            blocked = True
            if tool_name == "Read":
                suggestion = (
                    "  mcp__serena__get_symbols_overview  — module overview\n"
                    "  mcp__serena__find_symbol           — read a specific function/class\n"
                    "  mcp__serena__search_for_pattern    — search by regex/string"
                )
            elif tool_name == "Edit":
                suggestion = (
                    "  mcp__serena__replace_symbol_body   — replace a function/class body\n"
                    "  mcp__serena__insert_after_symbol   — insert code after a symbol\n"
                    "  mcp__serena__insert_before_symbol  — insert code before a symbol\n"
                    "  mcp__serena__rename_symbol         — rename a symbol project-wide"
                )
            elif tool_name == "Write":
                suggestion = (
                    "  Write is allowed for NEW .py files (the hook carves that out).\n"
                    "  For an EXISTING .py file, don't overwrite — edit via symbols:\n"
                    "    mcp__serena__replace_symbol_body\n"
                    "    mcp__serena__insert_after_symbol / insert_before_symbol"
                )

elif tool_name == "Grep":
    glob_param = str(tool_input.get("glob", ""))
    type_param = str(tool_input.get("type", ""))
    if "*.py" in glob_param or ".py" in glob_param or type_param == "py":
        blocked = True
        suggestion = (
            "  mcp__serena__search_for_pattern    — regex/string search in Python files\n"
            "  mcp__serena__find_symbol           — find a specific symbol by name\n"
            "  mcp__serena__find_referencing_symbols — find all callers of a symbol"
        )

elif tool_name == "Glob":
    pattern = str(tool_input.get("pattern", ""))
    if ".py" in pattern and not _is_hook_path(pattern):
        blocked = True
        suggestion = (
            "  mcp__serena__find_file             — locate a Python file by name\n"
            "  mcp__serena__list_dir              — browse project structure\n"
            "  mcp__serena__get_symbols_overview  — symbols in a specific file"
        )

elif tool_name == "Bash":
    command = str(tool_input.get("command", ""))
    if not _is_hook_path(command):
        # Heuristic — catches common in-place edits. Not a sandbox:
        # `find ... -exec sed -i {} \;` will slip through, and a quoted
        # string containing `> foo.py` false-positives. Acceptable for
        # a nudge hook; Serena is the preferred path regardless.
        edit_on_py_patterns = [
            # sed -i / sed -Ei / sed -i.bak touching a .py argument
            r"\bsed\s+\S*-\S*i[^|;&]*?\.py\b",
            # awk -i inplace with a .py argument
            r"\bawk\s+-i\s+inplace\b[^|;&]*?\.py\b",
            # perl -i / perl -pi with a .py argument
            r"\bperl\s+\S*-\S*i[^|;&]*?\.py\b",
            # output redirection > or >> to a .py target
            r"(?<![<>&])>{1,2}(?![>&])\s*\S*\.py\b",
            # tee writing to a .py target
            r"\btee\b[^|;&]*?\S+\.py\b",
        ]
        for rx in edit_on_py_patterns:
            if re.search(rx, command):
                blocked = True
                suggestion = (
                    "  Don't edit Python files via shell. Use Serena symbol tools:\n"
                    "    mcp__serena__replace_symbol_body   — replace a function/class body\n"
                    "    mcp__serena__insert_after_symbol   — insert code after a symbol\n"
                    "    mcp__serena__insert_before_symbol  — insert code before a symbol\n"
                    "    mcp__serena__rename_symbol         — rename a symbol project-wide\n"
                    "    mcp__serena__safe_delete_symbol    — remove a symbol\n"
                    "  For NEW .py files, use the built-in Write tool "
                    "(non-existent paths are carved out)."
                )
                break

if blocked:
    print(
        f"[Serena Guard] BLOCKED — {tool_name} on Python code is not allowed.\n"
        f"Serena MCP is running. Use it instead:\n"
        f"{suggestion}\n"
        f"Load schema first:  ToolSearch select:mcp__serena__<tool_name>",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(0)
