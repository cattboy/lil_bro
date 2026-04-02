# lil_bro — Backlog / ToDo

## Build pipeline

### [ ] Multi-arch PawnIO extraction + build.py arch flag

**Branch to target:** future sprint (post pawnio-cleanup)

**What:**
Update `tools/PawnIO_Latest_Check/update_pawnio.ps1` to preserve all 4
extracted `.sys` variants into architecture-specific subfolders:

    resources/extracted/
      x64/PawnIO.sys     ← machine type 0x8664 (currently PawnIO_2.sys, 136504 bytes)
      arm64/PawnIO.sys   ← machine type 0xAA64 (currently PawnIO.sys,   640608 bytes)

Instead of discarding non-x64 files with the temp dir, copy each arch's
first match (by machine type) into its own subfolder before cleanup.

**Why:**
`PawnIO_setup.exe` is a multi-arch installer — the embedded CAB contains
4 `.sys` files (2× x64, 2× ARM64). Currently non-x64 variants are discarded
after extraction. An ARM64 lil_bro build would need to re-run the full
extractor just to get a file we already had. Storing all variants once makes
multi-arch builds free at build time.

**build.py changes:**
- Add `--arch` flag (choices: `x64`, `arm64`; default: `x64`)
- Before step [3] (lhm-server build), copy
  `resources/extracted/<arch>/PawnIO.sys` → `tools/PawnIO/dist/PawnIO.sys`
- `run_pawnio_update()` passes `--arch` down so `update_pawnio.ps1` knows
  which subfolder to populate / validate (or re-extracts if missing)
- `lhm-server` build + `LhmServer.csproj` are unchanged — they always embed
  from `tools/PawnIO/dist/PawnIO.sys`; arch selection is purely upstream

**update_pawnio.ps1 changes:**
- Step 0 guard: check `resources/extracted/x64/PawnIO.sys` AND
  `resources/extracted/arm64/PawnIO.sys` for correct machine types before
  short-circuiting (both must be present and correct to skip extraction)
- Step 7: after selecting the x64 variant for the build, also copy the arm64
  variant to `resources/extracted/arm64/PawnIO.sys`; copy x64 to
  `resources/extracted/x64/PawnIO.sys`
- Final copy to `tools/PawnIO/dist/PawnIO.sys` uses the arch specified by
  `--arch` parameter (defaults to `x64`)

**.gitignore additions needed:**
    /tools/PawnIO_Latest_Check/resources/extracted/

**Acceptance criteria:**
- `python build.py` (no flags) behaves identically to today — x64 driver
- `python build.py --arch arm64` embeds the ARM64 driver in lhm-server.exe
- Re-running when both arch subfolders already have correct variants is a
  no-op (Step 0 exits early without downloading or re-extracting)
- Existing 312 tests continue to pass; new tests cover arch flag routing
  in `build.py` and the dual-subfolder copy logic in the ps1 script
