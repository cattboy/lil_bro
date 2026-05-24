#!/usr/bin/env python3
"""Find large Python files that may be candidates for refactoring.

Output: JSON array of {path, lines, first_docstring_line} sorted by line count desc.
Usage:
    python find_large_files.py --threshold 300 --root src/
    python find_large_files.py --threshold 500 --root src/
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path


def first_docstring_line(path: Path) -> str:
    """Return the first line of the module-level docstring, or empty string.

    Uses ast so we don't get fooled by string literals that look like docstrings
    deeper in the file. Returns "" on any parse error — we still want the file
    in the report, we just won't have a description for it.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return ""
    doc = ast.get_docstring(tree)
    if not doc:
        return ""
    return doc.strip().splitlines()[0]


def count_lines(path: Path) -> int:
    """Count total lines (matches `wc -l`)."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--threshold", type=int, default=300,
                    help="Minimum line count to include (default: 300)")
    ap.add_argument("--root", type=str, default="src/",
                    help="Directory to scan recursively (default: src/)")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"error: {root} does not exist", file=sys.stderr)
        return 1

    results: list[dict] = []
    for py_file in root.rglob("*.py"):
        # Skip caches and build artifacts — they're not refactorable.
        if any(part in {"__pycache__", ".venv", "build", "dist"} for part in py_file.parts):
            continue
        lines = count_lines(py_file)
        if lines >= args.threshold:
            results.append({
                "path": str(py_file).replace("\\", "/"),
                "lines": lines,
                "first_docstring_line": first_docstring_line(py_file),
            })

    results.sort(key=lambda r: r["lines"], reverse=True)
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
