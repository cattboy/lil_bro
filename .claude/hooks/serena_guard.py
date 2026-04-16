#!/usr/bin/env python3
"""
Serena Guard — PreToolUse hook.

Blocks Read / Edit / Write / Grep / Glob calls that target Python source
files and reminds Claude to use the appropriate Serena MCP tool instead.

Exit codes:
  0 — allow the tool call to proceed
  2 — block the tool call; stderr is shown to the model as feedback
"""
import json
import sys
from pathlib import Path

data = json.load(sys.stdin)
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

blocked = False
suggestion = ""

if tool_name in ("Read", "Edit", "Write"):
    path = str(tool_input.get("file_path", ""))
    if path.endswith(".py"):
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
    if ".py" in pattern:
        blocked = True
        suggestion = (
            "  mcp__serena__find_file             — locate a Python file by name\n"
            "  mcp__serena__list_dir              — browse project structure\n"
            "  mcp__serena__get_symbols_overview  — symbols in a specific file"
        )

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
