# Serena Safety During Refactor Chunks

The implementation phase mixes Serena symbol tools (for symbol-body edits) with built-in `Edit`/`Write` (for module-level lines — imports, constants, `__all__`, module docstrings). Serena's language server holds an in-memory copy of each `.py` file that stays synced **only for Serena's own edits**. Non-Serena edits desync the LS, and the next Serena symbol op then fails or writes stale content.

This document tells the implementation worker how to keep Serena in sync across chunks.

## The desync rule

The LS desyncs on:
- Any built-in `Edit` to a `.py` file
- Any built-in `Write` to a `.py` file
- Shell ops that modify `.py` files in place (`sed -i`, redirects, `rm`)
- Git working-tree ops: `checkout`, `rebase`, `reset --hard`

The LS does **not** desync on:
- A bare `git commit` (working tree unchanged)
- Serena's own symbol-edit tools (`replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol`, `rename_symbol`)
- Built-in `Read` (read-only)

## The recovery action

After any desync event, before the next Serena symbol op, call:

```
mcp__serena__restart_language_server
```

This re-indexes the file from disk. It's fast (~1 second for a single-file restart) and idempotent — safe to call extra times if you're not sure whether you desynced.

## Chunk patterns

### Pattern A — Symbol-only chunk (preferred when possible)
The chunk only edits symbol bodies. All edits via Serena. No restart needed.

### Pattern B — Mixed chunk (most common)
The chunk edits both symbol bodies and module-level lines (e.g. add an import, change a constant). **Order matters:**

1. Do **all Serena symbol edits first** on this file
2. Do **all built-in `Edit`s last** on this file
3. Before any further Serena op on this file (this chunk or the next): `restart_language_server`

If you reverse the order — built-in `Edit` first, then `replace_symbol_body` — the symbol edit will fail with `InvalidTextLocationError` or write into the wrong line range.

### Pattern C — Wholesale rewrite chunk
The chunk substantially rewrites the file (e.g. extracting the bulk of it to a new module and leaving a thin shim). Don't use Serena symbol tools for this — they fight the rewrite.

1. `Read` the file
2. Compose the new content in memory
3. `Write` the new content (overwrite — `Write` permits overwriting files Read in this session)
4. `restart_language_server` before any Serena op anywhere

### Pattern D — New file creation
Use built-in `Write` for new `.py` files (Serena's `create_text_file` is excluded in the `claude-code` context). Then `restart_language_server` before referencing the new file via Serena — Serena needs to index it before `find_symbol` and friends can see it.

## End-of-chunk checklist

The worker runs this after every chunk:

1. **Did this chunk include any non-Serena edit to a `.py` file?** (Built-in `Edit`, `Write`, or shell op)
   - **Yes** → `restart_language_server` before the next chunk's Serena ops on the affected file
   - **No** → skip restart, proceed

2. **Did this chunk create a new `.py` file?**
   - **Yes** → `restart_language_server` so Serena indexes the new file
   - **No** → skip restart

3. **Did the test gate (`pytest -k {basename}`) pass?**
   - **Yes** → commit, proceed
   - **No** → halt, ask the user

## What goes wrong if you skip this

- `replace_symbol_body` succeeds but writes the new body into the *old* line range, corrupting whatever was at those lines in the on-disk file
- `insert_after_symbol` inserts at the wrong place
- `find_symbol` returns metadata for symbols that no longer exist, leading to phantom edits
- These failures are silent in the LS but very loud at test time — usually as `ImportError`, `AttributeError`, or a test asserting on the wrong value

The 1-second restart is cheap insurance. When in doubt, restart. The worker is allowed to over-restart — wasted seconds beat corrupted files.
