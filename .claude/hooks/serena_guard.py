#!/usr/bin/env python3
"""
Serena Guard - PreToolUse hook.

Routes Python changes to the right tool: structural edits go through
Serena's symbol tools; the built-in tools handle what Serena can't.

  Edit  .py inside a def/class body  -> BLOCKED - use Serena
        (replace_symbol_body, insert_after/before_symbol, rename_symbol).
  Edit  .py at module level          -> allowed - imports, constants and
        module docstrings aren't symbols; Serena can't target them.
  Read  .py                          -> allowed - the built-in Edit tool
        requires a prior built-in Read, and the claude-code context
        excludes Serena's read_file. Prefer Serena overviews for
        navigation (CLAUDE.md guidance; not enforced here).
  Write new .py                      -> allowed - the claude-code context
        excludes create_text_file.
  Write existing .py                 -> BLOCKED - whole-file overwrite;
        edit it instead.
  Grep / Glob targeting .py          -> BLOCKED - use search_for_pattern,
        find_symbol, find_file.
  Bash in-place .py edit             -> BLOCKED - sed -i, output redirects,
        tee, awk/perl -i; use Serena symbol tools.

Carve-out: `.claude/` paths are infrastructure (hooks, skills, plugins);
Serena indexes only the project source tree, so they are never gated.

Exit codes:
  0 - allow the tool call to proceed
  2 - block the tool call; stderr is shown to the model as feedback
"""
import ast
import json
import re
import sys
from pathlib import Path

data = json.load(sys.stdin)
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})


def _is_claude_path(text: str) -> bool:
    return ".claude/" in text.replace("\\", "/")


def _py_symbol_ranges(src: str):
    """(start, end) line ranges of every function and class in `src` -
    1-based, inclusive, decorator lines included. None if `src` cannot
    be parsed."""
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    ranges = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno
            for deco in node.decorator_list:
                start = min(start, deco.lineno)
            ranges.append((start, node.end_lineno))
    return ranges


def _edit_hits_symbol(file_path: str, old_string: str):
    """Classify a built-in Edit by where its `old_string` lands.

      True   inside a function/class body  -> must go through Serena.
      False  module level only (imports, constants, docstrings)
             -> the built-in Edit is the right tool.
      None   undeterminable (unreadable file, syntax error, or the
             old_string is absent). Fail open: a file Serena can't parse
             is one its symbol tools can't edit either.
    """
    try:
        src = Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    ranges = _py_symbol_ranges(src)
    if ranges is None or not old_string or old_string not in src:
        return None
    idx = src.find(old_string)
    while idx != -1:                     # every occurrence - covers replace_all
        start = src.count("\n", 0, idx) + 1
        end = start + old_string.count("\n")
        if any(s <= end and start <= e for s, e in ranges):
            return True
        idx = src.find(old_string, idx + 1)
    return False


blocked = False
suggestion = ""

if tool_name in ("Read", "Edit", "Write"):
    path = str(tool_input.get("file_path", ""))
    if path.endswith(".py") and not _is_claude_path(path):

        if tool_name == "Read":
            # Allowed. The built-in Edit tool requires a prior built-in
            # Read of the file, and the claude-code context excludes
            # Serena's read_file - so Read must stay available. Navigation
            # should still prefer Serena overviews (CLAUDE.md guidance).
            pass

        elif tool_name == "Write":
            # New .py: allowed - the claude-code context excludes
            # create_text_file, so net-new creation is the IDE's job.
            # Existing .py: blocked - a whole-file overwrite can't be
            # scoped to a symbol; edit it instead.
            if Path(path).exists():
                blocked = True
                suggestion = (
                    "  Don't overwrite an existing .py file. Edit it:\n"
                    "    mcp__serena__replace_symbol_body  - for a symbol body\n"
                    "    built-in Edit                     - for module-level lines"
                )

        elif tool_name == "Edit":
            # Symbol-body edits go through Serena; module-level edits
            # (imports, constants, docstrings) use the built-in Edit.
            if _edit_hits_symbol(path, str(tool_input.get("old_string", ""))):
                blocked = True
                suggestion = (
                    "  This Edit lands inside a function/class body -\n"
                    "  use Serena's symbol tools instead:\n"
                    "    mcp__serena__replace_symbol_body   - replace a function/class body\n"
                    "    mcp__serena__insert_after_symbol   - insert code after a symbol\n"
                    "    mcp__serena__insert_before_symbol  - insert code before a symbol\n"
                    "    mcp__serena__rename_symbol         - rename a symbol project-wide\n"
                    "  Module-level edits (imports, constants) are allowed via Edit."
                )

elif tool_name == "Grep":
    grep_path = str(tool_input.get("path", ""))
    glob_param = str(tool_input.get("glob", ""))
    type_param = str(tool_input.get("type", ""))
    if not _is_claude_path(grep_path) and not _is_claude_path(glob_param):
        if "*.py" in glob_param or ".py" in glob_param or type_param == "py":
            blocked = True
            suggestion = (
                "  mcp__serena__search_for_pattern    - regex/string search in Python files\n"
                "  mcp__serena__find_symbol           - find a specific symbol by name\n"
                "  mcp__serena__find_referencing_symbols - find all callers of a symbol"
            )

elif tool_name == "Glob":
    pattern = str(tool_input.get("pattern", ""))
    if ".py" in pattern and not _is_claude_path(pattern):
        blocked = True
        suggestion = (
            "  mcp__serena__find_file             - locate a Python file by name\n"
            "  mcp__serena__list_dir              - browse project structure\n"
            "  mcp__serena__get_symbols_overview  - symbols in a specific file"
        )

elif tool_name == "Bash":
    command = str(tool_input.get("command", ""))
    if not _is_claude_path(command):
        # Heuristic - catches common in-place edits. Not a sandbox:
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
                    "    mcp__serena__replace_symbol_body   - replace a function/class body\n"
                    "    mcp__serena__insert_after_symbol   - insert code after a symbol\n"
                    "    mcp__serena__insert_before_symbol  - insert code before a symbol\n"
                    "    mcp__serena__rename_symbol         - rename a symbol project-wide\n"
                    "    mcp__serena__safe_delete_symbol    - remove a symbol\n"
                    "  For module-level lines or NEW .py files, use the built-in tools."
                )
                break

if blocked:
    print(
        f"[Serena Guard] BLOCKED - this {tool_name} must use a different tool:\n"
        f"{suggestion}\n"
        f"Serena schemas load via:  ToolSearch select:mcp__serena__<tool_name>",
        file=sys.stderr,
    )
    sys.exit(2)

sys.exit(0)
